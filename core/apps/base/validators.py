from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from core.apps.base.models import Med_Controlado, Radicacion
from core.apps.base.resources.api_calls import get_firebase_acta
from core.apps.base.resources.tools import encrypt, pretty_date, \
    update_rad_from_fbase
from core.settings import logger


def validate_status(resp_mcar: dict, rad: Radicacion) -> ValidationError:
    """
    Una vez validado que el radicado existe en la base de datos, entonces
    realiza las siguientes validaciones:
        - Consultando la API de medicar, verifica que tenga ssc
        - Caso si, actualiza el acta_entrega en base de datos
            - Verifica si tiene factura
            - Caso si, entonces, consulta en firebase
                - Si la respuesta es null, notifica que está en reparto
                - Sino, actualiza algunos campos y notifica que está entregado.
            - Si no tiene factura, notifica que en preparación.
        - Caso no, notifica simplemente que ya fue radicado.
    """
    radicado_dt = pretty_date(
        rad.datetime.astimezone(timezone.get_current_timezone())
    )
    logger.info(f"{rad.numero_radicado} radicado {radicado_dt}.")
    text_resp = ''
    if ssc := resp_mcar.get('ssc'):
        if not rad.acta_entrega:
            rad.acta_entrega = ssc
            rad.save()
        if factura := resp_mcar.get('factura'):
            # Radicado  tiene SSC, factura y está por confirmar si está firebase
            logger.info(f"{rad.numero_radicado} radicado con factura detectada.")
            if not rad.factura:
                rad.factura = factura
                rad.save()
            text_resp = f'Número de autorización {rad.numero_radicado} radicado ' \
                        f'{radicado_dt}.<br><br>Este domicilio se encuentra en reparto<br><br>' \
                        f'Si tiene alguna duda se puede comunicar con nosotros ' \
                        'al 3330333124 <br><br>'
            resp_fbase = get_firebase_acta(ssc)
            if resp_fbase and resp_fbase['state'] == 'Completed':
                # Radicado  tiene SSC, factura y está en firebase
                update_rad_from_fbase(rad, resp_fbase)
                rad.save()
                entregado_dt = pretty_date(
                    rad.despachado.astimezone(timezone.get_current_timezone())
                )
                logger.info(f"{rad.numero_radicado} actualizado,"
                            f" entregado {entregado_dt} (acta #{ssc}).")
                value = f"{encrypt(rad.numero_radicado)}aCmG{resp_fbase['actFileId'][::-1]}aCmG{encrypt(ssc)}"
                text_resp = (
                    f'Número de autorización {rad.numero_radicado} radicado '
                    f'{radicado_dt} y entregado {entregado_dt}<br><br>'
                    '<a style="text-decoration:none" href="{0}"">Ver soporte</a><br>'
                    '(Solo para personal autorizado)<br><br>'
                    'Si tiene alguna duda se puede comunicar con nosotros '
                    'al 3330333124 <br><br>').format(reverse('soporte', args=(value,)))

        else:
            # Radicado  tiene SSC pero no tiene factura y por eso se asume que no está en firebase
            logger.info(f"{rad.numero_radicado} radicado en preparación, acta #{ssc}.")
            text_resp = f'Número de autorización {rad.numero_radicado} radicado ' \
                        f'{radicado_dt}.<br><br>Este domicilio se encuentra en preparación<br><br>' \
                        'Si tiene alguna duda se puede comunicar con nosotros ' \
                        'al 3330333124 <br><br>'
    else:
        # Radicado no tiene SSC, se asume que no tiene factura ni está en firebase
        logger.info(f"{rad.numero_radicado} radicado sin acta aún.")
        text_resp = f'Número de autorización {rad.numero_radicado} radicado ' \
                    f'{radicado_dt}.\n\n Si tiene alguna duda se puede ' \
                    'comunicar con nosotros al 3330333124'
    raise forms.ValidationError(mark_safe(text_resp))


def validate_aut_exists(resp_eps: dict, num_aut: int) -> ValidationError:
    """
    Valida que la respuesta de la API de Cajacopi tenga información
    del número de autorización.
    """
    if resp_eps.get('codigo') == "1":
        logger.info(f"Número de autorización {num_aut} no encontrado.")
        raise forms.ValidationError(f"Número de autorización {num_aut} no encontrado\n\n"
                                    "Por favor verifique\n\n"
                                    "Si el número está correcto, comuníquese con cajacopi EPS\n"
                                    "al 01 8000 111 446")


def validate_structure(resp_eps: dict, num_aut: int) -> ValidationError:
    """
    Valida los siguientes puntos de la resuesta de la API de Cajacopi:
        - Tenga al menos 1 key.
        - Número de autorización menor a 20 digitos.
        - Key DOCUMENTO_ID menor a 32 digitos.
        - Key AFILIADO menor a 150 digitos.
    """
    inconsistencia = False
    if len(list(resp_eps.keys())) == 0 or len(str(num_aut)) > 20:
        inconsistencia = True
    else:
        for k, v in resp_eps.items():
            if k == 'DOCUMENTO_ID' and len(v) > 32:
                inconsistencia = True
                break
            if k == 'AFILIADO' and len(v) > 150:
                inconsistencia = True
                break
            if k == 'num_aut' and len(v) > 24:
                inconsistencia = True
                break

    if inconsistencia:
        logger.info(f"Incosistencia en radicado #{num_aut}.")
        raise forms.ValidationError(f"Detectamos un problema interno con este número de autorización\n"
                                    f"{num_aut}\n\n"
                                    "Comuníquese con Logifarma al 3330333124")


def validate_cums(resp_eps: dict, num_aut: int) -> ValidationError:
    """
    Valida los cums de los articulos provenientes de la API de Cajacopi
    y en caso de al menos uno encontrarse en la bd, entonces lanzará
    una excepción que para el usuario será un modal en la vista 2.
    """
    if cums_found := Med_Controlado.objects.filter(
            cum__in=[
                autorizacion['CUMS']
                for autorizacion in resp_eps['DETALLE_AUTORIZACION']
            ]
    ):
        obj_info = ''.join(
            f'<br>• {obj.nombre.title()}. {obj.cum} (CUM)' for obj in cums_found
        )
        logger.info(f"{num_aut} posee medicamentos controlados: {cums_found}.")
        text_resp = f'La autorización {num_aut} contiene ' \
                    f'medicamento(s) controlado(s):<br>' \
                    f"{obj_info}" \
                    f'<br><br> Por favor dirigete a uno de nuestros dispensarios.' \
                    f'<br><br> Si tiene alguna duda se puede comunicar con nosotros ' \
                    'al 3330333124 <br><br>'
        raise forms.ValidationError(mark_safe(text_resp))


def validate_status_afiliado(resp_eps: dict, num_aut: int) -> ValidationError:
    """
    Valida que el estado del afiliado sea "ACTIVO".
    """
    if resp_eps.get('ESTADO_AFILIADO') != 'ACTIVO':
        logger.info(f"EL estado del afiliado de radicado #{num_aut} no se encuentra activo.")
        raise forms.ValidationError("Afiliado no se encuentra activo.")


def validate_status_aut(resp_eps: dict, num_aut: int) -> ValidationError:
    """
    Valida que el estado de la autorización sea "PROCESADA"
    """
    if resp_eps.get('ESTADO_AUTORIZACION') != 'PROCESADA':
        logger.info(f"El estado de la autorización #{num_aut} es diferente de PROCESADA.")
        raise forms.ValidationError("El estado de la autorización no está activa.")
