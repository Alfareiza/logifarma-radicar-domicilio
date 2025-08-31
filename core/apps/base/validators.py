import threading
from datetime import datetime

from decouple import config, Csv
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
                        f'{radicado_dt}.<br><br>Este domicilio se encuentra en reparto.'
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
                    '(Solo para personal autorizado).').format(reverse('soporte', args=(value,)))
        elif rad_default.is_anulado:
            logger.info(f"{head_msg} y anulado, acta #{ssc}.")
            text_resp = f'Número de autorización {rad_default.numero_radicado} anulado.'
        else:
            # Radicado  tiene SSC pero no tiene factura y por eso se asume que no está en firebase
            logger.info(f"{head_msg} y se encuentra en preparación, acta #{ssc}.")
            text_resp = f'Número de autorización {rad_default.numero_radicado} radicado ' \
                        f'{radicado_dt}.<br><br>Este domicilio se encuentra en preparación.'
    else:
        # Radicado no tiene SSC, se asume que no tiene factura ni está en firebase
        logger.info(f"{head_msg} y aún no tiene acta.")
        text_resp = f'Número de autorización {rad_default.numero_radicado} radicado {radicado_dt}.'
    raise forms.ValidationError(
        message='Informando estado de radicado.',
        params={
            'modal_type': 'status_radicado',
            'modal_title': text_resp,
            'modal_body': "Para más información comunícate con nosotros al <a class='tel' href='tel:3330333124'>333 033 3124</a>.",
        })


def validate_aut_exists(resp_eps: dict, num_aut: int) -> ValidationError:
    """
    Valida que la respuesta de la API de Cajacopi tenga información
    del número de autorización.
    """
    if resp_eps.get('codigo') == "1":
        logger.info(f"Número de autorización {num_aut} no encontrado.")
        raise forms.ValidationError(
            message=f'Número de autorización {num_aut} no encontrado',
            params={
                'modal_type': 'autorizacion_no_existe',
                'modal_title': f"El número de autorización {num_aut} no ha sido encontrada, por favor verifica.",
                'modal_body': "Si el número es correcto comunícate con Cajacopi EPS al <a class='tel' href='tel:018000111446'>01 8000 111 446</a>.",
            }
        )


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
        raise forms.ValidationError(
            message='Problema con respuesta de API',
            params={'modal_type': 'api_unexpected_response',
                    'modal_title': f"Detectamos un problema interno con el número de autorización {num_aut}.",
                    'modal_body': "Para más información comunícate con nosotros al <a class='tel' href='tel:3330333124'>333 033 3124</a>."
                    })


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
                    f'medicamento(s) controlado(s):<br>{obj_info}' \
                    f'<br><br> Por favor dirigete a uno de nuestros dispensarios.'

        htmly = get_template(BASE_DIR / "core/apps/base/templates/notifiers/med_controlados.html")
        x = threading.Thread(target=notify, args=(
            'med-control', f'Medicamento controlado en autorización {num_aut}',
            htmly.render({'CUMS_FOUND': cums_found, 'NUMERO_AUTORIZACION': num_aut}),
        ))
        x.start()

        raise forms.ValidationError(
            message='Medicamento controlado.',
            params={
                'modal_type': 'medicamento_controlado',
                'modal_title': text_resp,
                'modal_body': "Para más información comunícate con nosotros al <a class='tel' href='tel:3330333124'>333 033 3124</a>.",
            })


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
            message='Estado de afiliado no es el esperado.',
            params={
                'modal_type': 'estado_afiliado',
                'modal_title': "Disculpa, el estado del afiliado no es el esperado. Por favor verifica e intenta nuevamente.",
                'modal_body': "Para más información comunícate con nosotros al <a class='tel' href='tel:3330333124'>333 033 3124</a>.",
            })


def validate_status_aut(resp_eps: dict, num_aut: int) -> ValidationError:
    """
    Valida que el estado de la autorización sea "PROCESADA"
    """
    if resp_eps.get('ESTADO_AUTORIZACION') not in ('PROCESADA', 'ACTIVA'):
        logger.info(msg := f"El estado de la autorización #{num_aut} es diferente de PROCESADA.")
        raise forms.ValidationError(
            message=msg,
            params={
                'modal_type': 'autorizacion_inactiva',
                'modal_title': "El estado de la autorización no está activa.",
                'modal_body': "Para más información comunícate con nosotros al <a class='tel' href='tel:3330333124'>333 033 3124</a>.",
            })


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
        logger.warning(msg := f"{info} no fue encontrado en {entidad}.")
        raise forms.ValidationError(
            message=msg,
            params={
                'modal_type': "status_radicado",
                'modal_title': f"No hemos podido encontrar información con ese documento en {entidad.title()}.",
                'modal_body': "Por favor verifica e intenta nuevamente o comunícate con nosotros al <a class='tel' href='tel:3330333124'>333 033 3124</a>.",
            })


def validate_email(email: str) -> ValidationError:
    """ Valida que el e-mail esté correcto. """
    import re
    regex = re.compile(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+')
    if not re.fullmatch(regex, email):
        raise forms.ValidationError(
            message='E-mail inválido.',
            params={
                'modal_type': "invalid_email",
                'modal_title': "E-mail inválido.",
            }
        )


def validate_empty_response(resp_eps: dict, documento: str, entidad: str) -> ValidationError:
    if not resp_eps:
        logger.info(msg := f"{documento} No se pudo obtener información del afiliado en {entidad.upper()}.")
        raise forms.ValidationError(
            message=msg,
            params={
                'modal_type': 'status_radicado',
                'modal_title': "Disculpa, en estos momentos no tenemos conexión.",
                'modal_body': "Por favor intentalo más tarde o en caso de dudas comunícate con nosotros al <a class='tel' href='tel:3330333124'>333 033 3124</a>.",
            })


def announce_pending_radicado_and_render_buttons(existing_radicados: 'QuerySet') -> ValidationError:
    """Raise an exception with "entiendo" button and "solicitar fórmula nueva" button conditionally."""
    rad = existing_radicados.first()
    template_btn = get_template('base/btn_in_modal.html')
    new_formula = template_btn.render({'id': 'new_formula', 'txt': 'Solicitar fórmula nueva',
                                       'bgcolor': 'white', 'txtcolor': '#2a57a9', 'widthbox': 22})
    raise forms.ValidationError(
        message='Informando estado de radicado.',
        params={
            'modal_type': 'autorizacion_pendiente_por_entregar',
            'modal_title': "Tenemos pendiente la entrega de artículo(s) con el "
                           f"número de radicación {rad.numero_autorizacion} solicitado "
                           f"{format(rad.datetime, when(rad.datetime))}.",
            'modal_body': f'<a class="tel" style="text-decoration:none" target="_blank" '
                          f'href="{rad.foto_formula}">Click aquí para ver la fórmula</a>. '
                          f'<b>No es necesario que la vuelvas a radicar</b>.',
            'second_button': 'solicitar_formula_nueva'
        })


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
    if scrapper.resultado_con_datos:
        return
    if not scrapper.resultado:
        logger.error(
            f"Error en afiliado {scrapper.tipo_documento}{scrapper.documento} con scrapper id {scrapper.id}")
        raise forms.ValidationError(
            message=f'Scrapper {scrapper.id} ha fallado.',
            params={
                'modal_type': 'scrapper_failed',
                'modal_title': "No pudimos procesar tu solicitud en este momento.",
                'modal_body': "Por favor intenta nuevamente más tarde o comunícate con nosotros al <a class='tel' href='tel:3330333124'>333 033 3124</a>.",
            })

    if msg := scrapper.resultado.get('MSG'):
        extra_txt = "Por favor, intenta nuevamente más tarde."
        match msg.lower():
            case 'usuario no posee autorizaciones en mutual ser.':
                msg = "No tienes solicitudes de fórmulas médicas pendientes por radicar."
            case _:
                msg = f"Encontramos una inconsistencia en nuestro sistema. {extra_txt}"
                logger.error(f"Revisar afiliado {scrapper.tipo_documento}{scrapper.documento} (scrapper {scrapper.id}):"
                             f" {scrapper.resultado.get('MSG')}")

        txt_mutualser = "Si consideras que tienes artículos por radicar, por favor comunícate con Mutualser EPS al número <a class='tel' href='tel:018000116882'>018000 116882</a> o <a class='tel' href='tel:#603'>#603</a>."
        txt_logi = "Para comunicarte con Logifarma, llámanos al <a class='tel' href='tel:3330333124'>333 033 3124</a>."
        raise forms.ValidationError(
            message='Scrapper falló y se obtuvo el mensaje de la falla.',
            params={
                'modal_type': 'scrapper_failed',
                'modal_title': msg,
                'modal_body': txt_logi if 'inconsistencia' in msg else f"{txt_mutualser}<br><br>{txt_logi}"
            })


def validate_dispensados(scrapper: ScrapMutualSer):
    """Organiza las autorizaciones encontradas en Zona Zer y las cruza con Medicar para determinar
    que hayan sido dispensadas o no."""
    dct = {'PENDIENTES': [], 'ENTREGADOS': []}
    for aut in scrapper.resultado:
        dct['ENTREGADOS' if aut['DISPENSADO'] else 'PENDIENTES'].append(aut)
    if not dct['PENDIENTES']:
        logger.info(f"{scrapper.tipo_documento}{scrapper.documento} scrap={scrapper.id} no tiene autorizaciones"
                    f" pendientes por radicar")
        raise forms.ValidationError(
            message='sin_autorizaciones_pendientes_por_radicar',
            params={
                'modal_type': 'status_radicado',
                'modal_title': "No tienes autorizaciones pendientes por radicar.",
                'modal_body': "Si consideras que tienes artículos por radicar, por favor comunícate con Mutualser al número <a class='tel' href='tel:018000116882'>018000 116882</a> o <a class='tel' href='tel:#603'>#603</a>.",
            })


def validate_numero_celular(cel: int):
    cel_str = str(cel)
    if len(cel_str) != 10:
        if len(cel_str) >= 11:
            raise forms.ValidationError(
                message='Numero muy largo.',
                params={
                    'modal_type': 'long_number',
                    'modal_title': "Teléfono incorrecto",
                    'modal_body': f"Revisa tu número de celular ({cel}), parece que tiene uno o más dígitos sobrando.",
                },
            )
        elif len(cel_str) >= 1:
            raise forms.ValidationError(
                message='Numero muy corto.',
                params={
                    'modal_type': 'short_number',
                    'modal_title': "Teléfono incorrecto",
                    'modal_body': f"Revisa tu número de celular ({cel}), parece que está incompleto o le faltan algunos dígitos.",
                },
            )

    if cel_str[0].startswith('57'):
        raise forms.ValidationError(
            message='Numero contiene indicativo de Colombia.',
            params={
                'modal_type': 'wrong_number',
                'modal_title': "Teléfono incorrecto",
                'modal_body': f"Número de celular incorrecto ({cel}), no es necesario que coloques el indicativo de Colombia.",
            },
        )

    numeros_fake = (300_000_0000,)
    if cel_str in tuple(map(str, numeros_fake)):
        raise forms.ValidationError(
            message='Numero no es de verdad.',
            params={
                'modal_type': 'fake_number',
                'modal_title': "Teléfono incorrecto",
                'modal_body': "Lo sentimos, debes colocar un número real para garantizar que todo saldrá bien.",
            },
        )

    if cel_str[0] != "3":
        logger.info(msg := f"Número de celular {cel} incorrecto.")
        raise forms.ValidationError(message=msg, params={
            'modal_type': 'unexpected_number',
            'modal_title': "Teléfono incorrecto",
            'modal_body': f"El número de celular que has digitado es incorrecto ({cel}).",
        }
                                    )
def direccion_min_length_validator(value):
    if len(value) < 5:
        raise ValidationError(
            message=f"Asegúrese de que este valor tenga como mínimo 5 caracteres (tiene {len(value)}).",
            code='short_number',
            params={
                'modal_type': 'short_number',
                'modal_title': f"Asegúrese de que este valor tenga como mínimo 5 caracteres (tiene {len(value)})."
            }
        )

# def validate_numeros_bloqueados(cel: int):
#     """Valida que el número ingresado no se encuentre entre los numeros bloqueados."""
#     numeros_bloqueados = config('CELULARES_NO_PERMITIDOS', cast=Csv(), default=())
#     if str(cel) in numeros_bloqueados:
#         raise forms.ValidationError(
#             message="Numero no permitido",  # Uso interno
#             params={
#                 'modal_type': 'blocked_number',
#                 'modal_title': f"Disculpa, el número de celular {cel} está restringido.",
#                 'modal_body': "Para más información comunícate con nosotros al <a class='tel' href='tel:3330333124'>333 033 3124</a>.",
#             }
#         )
