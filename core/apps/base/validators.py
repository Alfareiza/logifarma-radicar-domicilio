from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from core.apps.base.models import Radicacion
from core.apps.base.resources.api_calls import get_firebase_acta
from core.apps.base.resources.tools import encrypt, pretty_date
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
        rad.acta_entrega = ssc
        rad.save()
        if factura := resp_mcar.get('factura'):
            # Radicado  tiene SSC, factura y está por confirmar si está firebase
            logger.info(f"{rad.numero_radicado} radicado con factura detectada.")
            rad.factura = factura
            rad.save()
            text_resp = f'Número de autorización {rad.numero_radicado} radicado ' \
                        f'{radicado_dt}.<br><br>Este domicilio se encuentra en reparto<br><br>' \
                        f'Si tiene alguna duda se puede comunicar con nosotros ' \
                        'al 3330333124 <br><br>'
            resp_fbase = get_firebase_acta(ssc)
            if resp_fbase and resp_fbase['state'] == 'Completed':
                # Radicado  tiene SSC, factura y está en firebase
                rad.domiciliario_nombre = resp_fbase['nomDomi']
                rad.domicilario_ide = resp_fbase['docDomi']
                rad.despachado = datetime.strptime(
                    f"{resp_fbase['deliveryDate']} {resp_fbase['deliveryHour']}",
                    '%Y/%m/%d %H:%M:%S'
                )
                rad.domiciliario_empresa = resp_fbase['empDomi']
                rad.estado = resp_fbase['state']
                rad.factura = resp_fbase['invoice']
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
                    '<a style="text-decoration:none" href="{0}" target="_blank" rel="noopener noreferrer">Ver soporte</a><br>'
                    '(Solo para personal autorizado)<br><br>'
                    'Si tiene alguna duda se puede comunicar con nosotros '
                    'al 3330333124 <br><br>').format(reverse('soporte', args=(value, )))

        else:
            # Radicado  tiene SSC pero no tiene factura y por eso se asume que no está en firebase
            logger.info(f"{rad.numero_radicado} radicado en preparación acta (#{ssc}).")
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
