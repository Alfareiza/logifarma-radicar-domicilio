import threading
from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.template.loader import get_template
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from core.apps.base.models import Med_Controlado, Radicacion, ScrapMutualSer, Status
from core.apps.base.resources.api_calls import get_firebase_acta
from core.apps.base.resources.tools import encrypt, notify, pretty_date, \
    update_rad_from_fbase, has_accent, update_field, when
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
            - Si no tiene factura:
                - Si está anulado notifica que está anulado, sino
                - Notifica que está en preparación.
        - Caso no, notifica simplemente que ya fue radicado.
    """
    radicado_dt = pretty_date(
        rad_default.datetime.astimezone(timezone.get_current_timezone())
    )
    head_msg = f"{rad_default.numero_radicado} radicado {radicado_dt}"
    text_resp = ''
    if ssc := resp_mcar.get('ssc'):
        if not rad_default.acta_entrega:
            update_field(rad_default, 'acta_entrega', ssc)
        if factura := resp_mcar.get('factura'):
            # Radicado  tiene SSC, factura y está por confirmar si está firebase
            logger.info(f"{head_msg} y una factura ha sido detectada.")
            if not rad_default.factura:
                update_field(rad_default, 'factura', factura)
            text_resp = f'Número de autorización {rad_default.numero_radicado} radicado ' \
                        f'{radicado_dt}.<br><br>Este domicilio se encuentra en reparto<br><br>' \
                        f'Si tiene alguna duda se puede comunicar con nosotros ' \
                        'al 3330333124 <br><br>'
            resp_fbase = get_firebase_acta(ssc)
            if resp_fbase and resp_fbase['state'] == 'Completed':
                # Radicado  tiene SSC, factura y está en firebase
                update_rad_from_fbase(rad_default, resp_fbase)
                entregado_dt = pretty_date(
                    rad_default.despachado.astimezone(timezone.get_current_timezone())
                )
                logger.info(f"{head_msg}, actualizado en bd que fue entregado {entregado_dt} (acta #{ssc}).")
                value = f"{encrypt(rad_default.numero_radicado)}aCmG{resp_fbase['actFileId'][::-1]}aCmG{encrypt(ssc)}"
                text_resp = (
                    f'Número de autorización {rad_default.numero_radicado} radicado '
                    f'{radicado_dt} y entregado {entregado_dt}<br><br>'
                    '<a style="text-decoration:none" href="{0}"">Ver soporte</a><br>'
                    '(Solo para personal autorizado)<br><br>'
                    'Si tiene alguna duda se puede comunicar con nosotros '
                    'al 3330333124 <br><br>').format(reverse('soporte', args=(value,)))
        elif rad_default.is_anulado:
            logger.info(f"{head_msg} y anulado, acta #{ssc}.")
            text_resp = f'Número de autorización {rad_default.numero_radicado} anulado.' \
                        '<br><br>Si tiene alguna duda se puede comunicar con nosotros ' \
                        'al 3330333124 <br><br>'
        else:
            # Radicado  tiene SSC pero no tiene factura y por eso se asume que no está en firebase
            logger.info(f"{head_msg} y se encuentra en preparación, acta #{ssc}.")
            text_resp = f'Número de autorización {rad_default.numero_radicado} radicado ' \
                        f'{radicado_dt}.<br><br>Este domicilio se encuentra en preparación.<br><br>' \
                        'Si tiene alguna duda se puede comunicar con nosotros ' \
                        'al 3330333124 <br><br>'
    else:
        # Radicado no tiene SSC, se asume que no tiene factura ni está en firebase
        logger.info(f"{head_msg} y aún no tiene acta.")
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
        logger.info(f"{id_transaction} Estado del afiliado no es activo, sino {resp_eps.get(name_key)!r}.")
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
    :param entidad: 'cajacopi' o 'fomag' o 'mutualser'
    :param resp: Respuesta de la API al ser consultada.
    :param info: Representación del tipo de identificación y su valor.
                Ej: 'CC:123456789'
    """
    if resp.get('NOMBRE') and 'no existe' in resp['NOMBRE']:
        logger.warning(f"{info} no fue encontrado en {entidad}.")
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


def validate_empty_response(resp_eps: dict, documento: str, entidad: str) -> ValidationError:
    if not resp_eps:
        logger.info(f"{documento} No se pudo obtener información del afiliado en {entidad.upper()}.")
        raise forms.ValidationError(mark_safe("Disculpa, en estos momentos no tenemos conexión<br><br>"
                                              "Por favor intentalo más tarde o en caso de dudas, <br>"
                                              "comunícate con nosotros al <br>333 033 3124"))


def announce_pending_radicado_and_render_buttons(existing_radicados: 'QuerySet') -> ValidationError:
    """Raise an exception with "entiendo" button and "solicitar fórmula nueva" button conditionally."""
    rad = existing_radicados.first()
    template_btn = get_template('base/btn_in_modal.html')
    entiendo = template_btn.render({'id': 'entiendo', 'txt': 'Entiendo', 'bgcolor': '#2a57a9',
                                    'txtcolor': 'white', 'widthbox': 70})
    new_formula = template_btn.render({'id': 'new_formula', 'txt': 'Solicitar fórmula nueva',
                                       'bgcolor': 'white', 'txtcolor': '#2a57a9', 'widthbox': 22})
    raise forms.ValidationError(mark_safe("Tenemos pendiente la entrega de medicamento(s) con el "
                                          f"número de radicación {rad.numero_autorizacion} solicitado "
                                          f"{format(rad.datetime, when(rad.datetime))}.<br><br>"
                                          f'<a style="text-decoration:none" target="_blank" '
                                          f'href="{rad.foto_formula}"">Click aquí para ver la fórmula</a><br><br>'
                                          f'<b>No es necesario que la vuelvas a radicar</b><br><br>'
                                          f'{entiendo}<br>{new_formula}<br>'))


def announce_articulos_por_autorizacion(existing_radicados: 'QuerySet') -> ValidationError:
    """Raise an exception with "entiendo" button and "solicitar fórmula nueva" button conditionally."""
    # rad = existing_radicados.first()
    template_btn = get_template('base/btn_in_modal.html')
    entiendo = template_btn.render({'id': 'entiendo', 'txt': 'Entiendo', 'bgcolor': '#2a57a9',
                                    'txtcolor': 'white', 'widthbox': 70})
    raise forms.ValidationError(mark_safe("No tienes artículos pendientes por radicar."
                                          # f"número de radicación {rad.numero_autorizacion} solicitado "
                                          # f"{format(rad.datetime, when(rad.datetime))}."
                                          f'<br><br><b>No es necesario que la vuelvas a radicar</b><br><br>'
                                          f'{entiendo}<br>'))


def validate_recent_radicado(tipo: str, value: str, convenio: str):
    """Check that the user with more than one radicado is notified that he has pending filings."""
    existing_radicados = Radicacion.objects.filter(
        paciente_cc=f'{tipo}{value}', convenio=convenio, acta_entrega__isnull=True
    ).only('id', 'datetime', 'paciente_data')
    existing_radicados_count = existing_radicados.count()
    if existing_radicados_count >= 1:
        logger.info(f"{tipo}{value} ha sido avisado que tiene {existing_radicados_count} radicacion(es) pendiente(es).")
        announce_pending_radicado_and_render_buttons(existing_radicados)


def validate_resp_zona_ser(scrapper: ScrapMutualSer):
    """Given the portal response as a dict like this:
        {
            "status": "SUCCESS",
            "result": [
                {
                    "CONSECUTIVO_PROCEDIMIENTO": "2025050533572734",
                    "NUMERO_SOLICITUD": "33572734",
                    "FECHA_SOLICITUD": "05/05/2025",
                    "ESTADO_AUTORIZACION": "APROBADO",
                    "NUMERO_AUTORIZACION": "123123123",
                    "DETALLE_AUTORIZACION": [
                        {
                            "NOMBRE_PRODUCTO": "M02625 APIXABAN 5.MG/1.U TABLETA RECUBIERTA",
                            "CANTIDAD": "60"
                        }
                    ]
                },
                {
                    "CONSECUTIVO_PROCEDIMIENTO": "2025050533572276",
                    "NUMERO_SOLICITUD": "33572276",
                    "FECHA_SOLICITUD": "05/05/2025",
                    "ESTADO_AUTORIZACION": "APROBADO",
                    "NUMERO_AUTORIZACION": "23423431",
                    "DETALLE_AUTORIZACION": [
                        {
                            "NOMBRE_PRODUCTO": "M02087 BETAHISTINA 24.MG/1.U TABLETA",
                            "CANTIDAD": "30"
                        }
                    ]
                },
                {
                    "CONSECUTIVO_PROCEDIMIENTO": "2025040233089773",
                    "NUMERO_SOLICITUD": "33089773",
                    "FECHA_SOLICITUD": "02/04/2025",
                    "ESTADO_AUTORIZACION": "APROBADO",
                    "NUMERO_AUTORIZACION": "41341234123412341",
                    "DETALLE_AUTORIZACION": [
                        {
                            "NOMBRE_PRODUCTO": "M02625 APIXABAN 5.MG/1.U TABLETA RECUBIERTA",
                            "CANTIDAD": "60"
                        }
                    ]
                }
            ]
        }
    Validate the pending deliveries on medicare api.
    """
    if scrapper.texto_error == '' and not scrapper.resultado.get('MSG'):
        return
    if not scrapper.resultado:
        logger.error(
            f"Error en afiliado {scrapper.tipo_documento}{scrapper.documento} con scrapper id {scrapper.id}")
        raise forms.ValidationError(mark_safe("No pudimos procesar tu solicitud en este momento. Por favor, "
                                              "intenta nuevamente más tarde. Gracias por tu comprensión!.<br><br>"
                                              "Comunícate con nostros al número <br>333 033 3124"))

    if msg := scrapper.resultado.get('MSG'):
        extra_txt = "Por favor, intenta nuevamente más tarde."
        match msg.lower():
            case 'usuario no posee autorizaciones en mutual ser.':
                msg = "No tienes solicitudes de artículos pendientes por radicar. <br><br>Si consideras que tienes artículos por radicar, por favor comunícate con Mutualser al número 018000 116882 o #603<br><br>"
            case _:
                msg = f"Encontramos una inconsistencia en nuestro sistema. {extra_txt}"
                logger.error(f"Revisar afiliado {scrapper.tipo_documento}{scrapper.documento} (scrapper {scrapper.id}):"
                             f" {scrapper.resultado.get('MSG')}")

        raise forms.ValidationError(mark_safe(f"{msg} <br>Gracias por tu comprensión!.<br><br>"
                                              "Comunícate con nostros al número <br>333 033 3124"))


def validate_dispensados(scrapper: ScrapMutualSer):
    """Organiza las autorizaciones encontradas en Zona Zer y las cruza con Medicar para determinar
    que hayan sido dispensadas o no."""
    dct = {'PENDIENTES': [], 'ENTREGADOS': []}
    for aut in scrapper.resultado:
        dct['ENTREGADOS' if aut['DISPENSADO'] else 'PENDIENTES'].append(aut)
    if not dct['PENDIENTES']:
        entiendo = get_template('base/btn_in_modal.html').render(
            {'id': 'entiendo', 'txt': 'Entiendo', 'bgcolor': '#2a57a9', 'txtcolor': 'white', 'widthbox': 70}
        )
        logger.info(f"{scrapper.tipo_documento}{scrapper.documento} scrap={scrapper.id} no tiene autorizaciones"
                    f" pendientes por radicar")
        raise forms.ValidationError(
            mark_safe(f"No tienes autorizaciones pendientes por radicar<br><br>"
                      "Si consideras que tienes artículos por radicar, por favor comunícate "
                      "con Mutualser al número <br>018000 116882 o #603<br><br>"
                      f"<br>{entiendo}<br>"))


def validate_numero_celular(cel):
    cel_str = str(cel)
    if cel_str[0].startswith('57'):
        raise forms.ValidationError(
            f"Número de celular incorrecto, no es necesario que coloques el indicativo de Colombia."
            f":\n{cel}")

    if len(cel_str) != 10:
        if len(cel_str) == 11:
            raise forms.ValidationError(f"Revisa tu número de celular, parece que tiene un dígito de más:\n{cel}")
        elif len(cel_str) > 11:
            raise forms.ValidationError(
                f"Revisa tu número de celular, parece que tiene más de un dígito de más:\n{cel}")
        elif len(cel_str) > 1:
            raise forms.ValidationError(f"Revisa tu número de celular, parece que está incompleto o le"
                                        f" faltan algunos dígitos:\n{cel}")

    numeros_fake = ('30000000',)
    if cel_str in numeros_fake:
        raise forms.ValidationError(
            f"Lo sentimos, debes colocar un número real para garantizar que todo saldrá bien:\n{cel}")

    if cel_str[0] != "3":
        logger.info(f"Número de celular {cel} incorrecto.")
        raise forms.ValidationError(f"Número de celular incorrecto:\n{cel}")
