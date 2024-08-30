import threading
from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.template.loader import get_template
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from core.apps.base.models import Med_Controlado, Radicacion
from core.apps.base.resources.api_calls import get_firebase_acta
from core.apps.base.resources.tools import encrypt, notify, pretty_date, \
    update_rad_from_fbase, has_accent, update_field
from core.settings import BASE_DIR, logger


def validate_status(resp_mcar: dict, rad_default: Radicacion) -> ValidationError:
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
        rad_default.datetime.astimezone(timezone.get_current_timezone())
    )
    logger.info(f"{rad_default.numero_radicado} radicado {radicado_dt}.")
    text_resp = ''
    rad_server = Radicacion.objects.using('server').filter(numero_radicado=rad_default.numero_radicado).first()
    if ssc := resp_mcar.get('ssc'):
        if not rad_default.acta_entrega:
            update_field(rad_default, 'acta_entrega', ssc)
            update_field(rad_server, 'acta_entrega', ssc)
        if factura := resp_mcar.get('factura'):
            # Radicado  tiene SSC, factura y está por confirmar si está firebase
            logger.info(f"{rad_default.numero_radicado} radicado con factura detectada.")
            if not rad_default.factura:
                update_field(rad_default, 'factura', factura)
                update_field(rad_server, 'factura', factura)
            text_resp = f'Número de autorización {rad_default.numero_radicado} radicado ' \
                        f'{radicado_dt}.<br><br>Este domicilio se encuentra en reparto<br><br>' \
                        f'Si tiene alguna duda se puede comunicar con nosotros ' \
                        'al 3330333124 <br><br>'
            resp_fbase = get_firebase_acta(ssc)
            if resp_fbase and resp_fbase['state'] == 'Completed':
                # Radicado  tiene SSC, factura y está en firebase
                update_rad_from_fbase(rad_default, resp_fbase)
                update_rad_from_fbase(rad_server, resp_fbase)
                entregado_dt = pretty_date(
                    rad_default.despachado.astimezone(timezone.get_current_timezone())
                )
                logger.info(f"{rad_default.numero_radicado} actualizado,"
                            f" entregado {entregado_dt} (acta #{ssc}).")
                value = f"{encrypt(rad_default.numero_radicado)}aCmG{resp_fbase['actFileId'][::-1]}aCmG{encrypt(ssc)}"
                text_resp = (
                    f'Número de autorización {rad_default.numero_radicado} radicado '
                    f'{radicado_dt} y entregado {entregado_dt}<br><br>'
                    '<a style="text-decoration:none" href="{0}"">Ver soporte</a><br>'
                    '(Solo para personal autorizado)<br><br>'
                    'Si tiene alguna duda se puede comunicar con nosotros '
                    'al 3330333124 <br><br>').format(reverse('soporte', args=(value,)))

        else:
            # Radicado  tiene SSC pero no tiene factura y por eso se asume que no está en firebase
            logger.info(f"{rad_default.numero_radicado} radicado en preparación, acta #{ssc}.")
            text_resp = f'Número de autorización {rad_default.numero_radicado} radicado ' \
                        f'{radicado_dt}.<br><br>Este domicilio se encuentra en preparación<br><br>' \
                        'Si tiene alguna duda se puede comunicar con nosotros ' \
                        'al 3330333124 <br><br>'
    else:
        # Radicado no tiene SSC, se asume que no tiene factura ni está en firebase
        logger.info(f"{rad_default.numero_radicado} radicado sin acta aún.")
        text_resp = f'Número de autorización {rad_default.numero_radicado} radicado ' \
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


def validate_med_controlados(resp_eps: dict, num_aut: int) -> ValidationError:
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

        htmly = get_template(BASE_DIR / "core/apps/base/templates/notifiers/med_controlados.html")
        x = threading.Thread(target=notify, args=(
            'med-control', f'Medicamento controlado en autorización {num_aut}',
            htmly.render({'CUMS_FOUND': cums_found, 'NUMERO_AUTORIZACION': num_aut}),
        ))
        x.start()

        raise forms.ValidationError(mark_safe(text_resp))


def validate_status_afiliado(resp_eps: dict, name_key: str, id_transaction: str) -> ValidationError:
    """
    Valida que el estado del usuario sea 'ACTIVO' o 'PROTECCION LABORAL'.
    Esta función es llamada para cuando el usuario está en el flujo con
    número de autorización o sin.
    :param resp_eps: Respuesta de API (flujo con autorización) o de medicar o
                     de cajacopi (flujo sin autorización).
    :param name_key: Nombre de la llave en el diccionario, que es la respuesta de la API.
                    Ej.: 'ESTADO_AFILIADO' o 'ESTADO'
    :param id_transaction: Representa la identificación en la transacción.
                            - En el caso del flujo CON autorización es el número de la
                             autorización.
                            - En el caso del flujo SIN autorización es el
                              {tipo_identificacion}{valor_identificacion}.
    """
    if resp_eps.get(name_key) not in ('ACTIVO', 'PROTECCION LABORAL'):
        logger.info(f"El estado del afiliado #{id_transaction} no se encuentra activo."
                    f" Estado={resp_eps.get(name_key)}.")
        raise forms.ValidationError(
            mark_safe("Disculpa, el estado del afiliado no es el esperado.<br><br>"
                      "Por favor verifica e intenta nuevamente."))


def validate_status_aut(resp_eps: dict, num_aut: int) -> ValidationError:
    """
    Valida que el estado de la autorización sea "PROCESADA"
    """
    if resp_eps.get('ESTADO_AUTORIZACION') not in ('PROCESADA', 'ACTIVA'):
        logger.info(f"El estado de la autorización #{num_aut} es diferente de PROCESADA.")
        raise forms.ValidationError("El estado de la autorización no está activa.")


def validate_identificacion_exists(entidad: str, resp: dict, info: str) -> ValidationError:
    """
    Valida que la identificacion existe, considerando la respuesta
    de la API.
    :param resp: Respuesta de la API al ser consultada.
    :param info: Representación del tipo de identificación y su valor.
                Ej: 'CC:123456789'
    """
    if resp.get('NOMBRE') and 'no existe' in resp['NOMBRE']:
        logger.info(f"El afiliado {info} no fue encontrado en {entidad}.")
        raise forms.ValidationError(
            mark_safe(f"Disculpa, no hemos podido encontrar información con ese documento en {entidad.title()}.<br><br>"
                      "Por favor verifica e intenta nuevamente."))


def validate_email(email: str) -> ValidationError:
    """ Valida que el e-mail esté correcto. """
    if has_accent(email):
        raise forms.ValidationError(mark_safe("E-mail inválido."))

    import re
    regex = re.compile(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+')
    if not re.fullmatch(regex, email):
        raise forms.ValidationError(mark_safe("E-mail inválido."))


def validate_empty_empty_response(resp_eps: dict, documento: str) -> ValidationError:
    if not resp_eps:
        logger.info(f"No se pudo obtener información del usuario {documento}.")
        raise forms.ValidationError(mark_safe("Disculpa, en estos momentos no tenemos conexión<br><br>"
                                              "Por favor intentalo más tarde o en caso de dudas, <br>"
                                              "comunícate con nosotros al <br>333 033 3124"))
