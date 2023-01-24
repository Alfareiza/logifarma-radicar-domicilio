from django.core.mail import EmailMessage

from core import settings
from core.apps.base.models import Radicacion, Municipio, Barrio
from core.settings import BASE_DIR, logger


def convert_bytes(size):
    """ Convert bytes to KB, or MB or GB"""
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return "%3.1f %s" % (size, x)
        size /= 1024.0


def read_json(pathfile):
    """Read a json and return a dict"""
    import json
    fp = BASE_DIR / f'core/apps/base/{pathfile}'
    with open(fp) as file:
        data = json.load(file)

    return data


def del_file(filepath):
    """
    Elimina el archivo indicado.
    :param filepath: 'tmp_logifrm/formula_medica.png'
    :return: None
    """
    try:
        import os
        os.remove(filepath)
        logger.info(f"Imagen ==> {filepath} <== eliminada")
    except FileNotFoundError as e:
        logger.error('Error al borrar el archivo: ', e)


def parse_agent(agent: str) -> str:
    """
    Recibe el agente que hace el request y devuelve algunos valores
    :param agent: Representación del agent
    :return: Agente resumido
    >>> parse_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36')
    '(Windows NT 10.0; Win64; x64) Chrome/108.0.0.0'
    >>> parse_agent('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/17.0 Chrome/96.0.4664.104 Safari/537.36')
    '(X11; Linux x86_64) SamsungBrowser/17.0'
    >>> parse_agent('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36')
    '(X11; Linux x86_64) Chrome/107.0.0.0'
    >>> parse_agent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15(KHTML, like Gecko) Version/15.2 Safari/605.1.15')
    '(Macintosh; Intel Mac OS X 10_15_6) Version/15.2'
    >>> parse_agent('Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Mobile Safari/537.36')
    '(Linux; Android 13; Pixel 6) Chrome/108.0.0.0'
    """
    try:
        start_os = agent.find('(')
        end_os = agent.find(')')
        os_device = agent[start_os:end_os + 1]
        start_brw = len(agent) - agent[::-1].find(')') + 1
        brw_device = agent[start_brw:].split(' ')[0]
    except Exception as e:
        logger.warning("Parsear el agent=", agent, "ERROR=", e)
        return agent
    return f'{os_device}({brw_device})'


def guardar_info_bd(**kwargs):
    """
    Guarda radicado en base de datos
    :param kwargs: Información final del wizard + ip:
            Ejemplo:
            {
              "TIPO_IDENTIFICACION": "CC",
              "DOCUMENTO_ID": "12340316",
              "AFILIADO": "GUTIERREZ TEIXEIRA JACKSON WOH",
              "ESTADO_AFILIADO": "ACTIVO",
              "SEDE_AFILIADO": "BARRANCABERMEJA",
              "REGIMEN": "SUBSIDIADO",
              "DIRECCION": "CL 123  45 678",
              "CORREO": "jackson.gutierrez.teixeira123456789@gmail.com",
              "TELEFONO": "4019255",
              "CELULAR": "4014652512",
              "ESTADO_AUTORIZACION": "PROCESADA",
              "FECHA_AUTORIZACION": "15/11/2022",
              "MEDICO_TRATANTE": "FRANK LAMPARD",
              "MIPRES": "0",
              "DIAGNOSTICO": "D571-ANEMIA FALCIFORME SIN CRISIS",
              "DETALLE_AUTORIZACION": [
                {
                  "CUMS": "20158642-1",
                  "NOMBRE_PRODUCTO": "RIVAROXABAN 20MG TABLETA RECUBIERTA",
                  "CANTIDAD": "30"
                },
                {
                  "CUMS": "42034-1",
                  "NOMBRE_PRODUCTO": "HIDROXIUREA 500MG CAPSULA",
                  "CANTIDAD": "60"
                }
              ],
              "municipio": "objeto",
              "barrio": "Porvenir",
              "direccion": "Am 1234568",
              "celular": 3212125236,
              "email": "alfareiza@gmail.com",
              "NUMERO_AUTORIZACION": 99999999
            }
    :return:
    """
    rad = kwargs.pop('NUMERO_AUTORIZACION', None)
    if Radicacion.objects.filter(numero_radicado=str(rad)).exists():
        logger.info(f"Número de radicación {rad} ya existe!.")
        return
    municipio = kwargs.pop('municipio').name.lower()
    logger.info(f"Guardando radicación # {rad}")
    try:
        Radicacion.objects.create(numero_radicado=str(rad),
                                  municipio=Municipio.objects.get(
                                      name__iexact=municipio
                                  ),
                                  barrio=Barrio.objects.filter(
                                      municipio__name__iexact=municipio
                                  ).get(name=kwargs.pop('barrio', None).lower()),
                                  cel_uno=kwargs.pop('celular', None),
                                  cel_dos=None,
                                  email=kwargs.pop('email', None),
                                  direccion=kwargs.pop('direccion', None),
                                  ip=kwargs.pop('ip', None),
                                  paciente_nombre=kwargs.pop('AFILIADO', None),
                                  paciente_cc=kwargs.pop('DOCUMENTO_ID', None),
                                  paciente_data=kwargs)
        logger.info("Radicación guardada con éxito!")
    except Exception as e:
        notify('error-bd', f"ERROR GUARDANDO RADICACION {rad} EN BASE DE DATOS", e)
        logger.error(f"Error guardando radicación"
                     f" ({kwargs.get('NUMERO_AUTORIZACION')}): ", e)


def notify(reason: str, subject: str, body: str):
    """
    Función que envía un correo notificando algo
    :param reason: Puede ser error-bd o error-api
    :param subject: Asunto del correo
    :param body: Cuerpo del Correo
    :return: Nada
    """
    if reason == 'error-bd':
        msg = 'Correo enviado notificando problema con API'
    elif reason == 'error-api':
        msg = 'Correo enviado notificando problema al guardar en BD'

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=f"Logs Domicilios Logifarma <{settings.EMAIL_HOST_USER}>",
        to=['alfareiza@gmail.com', 'logistica@logifarma.co']
    )

    if sent := email.send(fail_silently=False):
        logger.error(msg)
