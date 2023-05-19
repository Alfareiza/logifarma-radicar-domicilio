import threading
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import pytz
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

        os_device.find(';')
        os_device.find(')')
        device = os_device[os_device.find(';') + 2:os_device.find(')')]

    except Exception as e:
        logger.warning("Parsear el agent=", agent, "ERROR=", e)
        return agent
    return f"({device})"


def is_file_valid(url: str, rad: str) -> bool:
    """
    Validate if the file is valid.
    When a file is valid?
        - THe url is reachable.
        - His size is more than 0 KB.
        - His pages have content.
    :param name: Number of radicado
                 Ex.: 855800017788
    :param url: Url of the file.
                Ex.: "https://genesis.cajacopieps.com/temp/63dcxy1234560fa.pdf"
    :return: True or False
    """
    if not url:
        logger.info(f'{rad} URL NO detectada en radicado.')
        return True
    else:
        logger.info(f'{rad} URL detectada en radicado: {url}')
        return False


def download_file(download_url, filename):
    """
    Download a file into the tmp/ folder of the project
    with the name of the autorization. Ex.: 857300123456789.pdf
    :param download_url: "https://genesis.cajacopieps.com/temp/XYd1112120fb6a.pdf"
    :param filename: 857300123456789
    :return:
    """
    try:
        Path(settings.MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
        filepath = settings.MEDIA_ROOT / f"{filename}.pdf"
        response = urllib.request.urlopen(download_url)
        with open(filepath, 'wb') as file:
            file.write(response.read())
    except Exception as e:
        logger.error('Error descargando archivo:', e)
        return ''
    else:
        return filepath


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
        logger.info(f"{rad} Número de radicación ya existe!.")
        return
    municipio = kwargs.pop('municipio').name.lower()

    email = kwargs.pop('email', None)
    if email:
        email = email[0]

    logger.info(f"{rad} Guardando radicación.")
    try:
        Radicacion.objects.create(
            # creado=datetime.now(tz=pytz.timezone("America/Bogota")),
            numero_radicado=str(rad),
            municipio=Municipio.objects.get(
                  name__iexact=municipio
                ),
            barrio=Barrio.objects.filter(
                municipio__name__iexact=municipio
                ).get(
                name=kwargs.pop('barrio', None).lower()),
            cel_uno=kwargs.pop('celular', None),
            cel_dos=kwargs.pop('whatsapp', None),
            email=email,
            direccion=kwargs.pop('direccion', None),
            ip=kwargs.pop('ip', None),
            paciente_nombre=kwargs.pop('AFILIADO', None),
            paciente_cc=kwargs.pop('DOCUMENTO_ID', None),
            paciente_data=kwargs)
        logger.info(f"{rad} Radicación guardada con éxito!")
    except Exception as e:
        notify('error-bd',
               f"ERROR GUARDANDO RADICACION {rad} EN BASE DE DATOS", e)
        logger.error(
            f"{kwargs.get('NUMERO_AUTORIZACION')} Error guardando radicación: {e}")


def discover_rad(body) -> str:
    """
    Busca el radicado en el cuerpo del correo.
    :param body:
    :return: # de radicado
    """
    import re
    if expr := re.findall("\d{9}\d+", body):
        return expr[0]
    return ''


def notify(reason: str, subject: str, body: str,
           to=None,
           bcc: list = []):
    """
    Envía un correo notificando algo.
    :param to: Para quien será enviado el correo.
    :param bcc: Copia oculta.
    :param reason: Puede ser:
                    'error-bd'
                    'error-api'
                    'error-archivo-url'
                    'error-email'
                    'check-acta'
                    'check-aut'
    :param subject: Asunto del correo
    :param body: Cuerpo del Correo
    :return: Nada
    """
    if to is None:
        to = ['alfareiza@gmail.com', 'logistica@logifarma.co']
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=f"Logs Domicilios Logifarma <{settings.EMAIL_HOST_USER}>",
        to=to,
        bcc=bcc
    )
    from django.utils.safestring import SafeString
    if isinstance(body, SafeString):
        email.content_subtype = "html"

    rad = discover_rad(body) or discover_rad(subject)

    if sent := email.send(fail_silently=False):
        msg = {
            'error-bd': '{} Correo enviado notificando problema al guardar en BD.',
            'error-api': '{} Correo enviado notificando problema con API.',
            'error-archivo-url': 'Correo enviado notificando radicado sin archivo.',
            'error-email': 'Correo enviado notificando problema al enviar e-mail de confirmación.',
            'check-acta': 'Correo enviado con reporte de chequeo de actas.',
            'check-aut': '{} Correo de alerta de autorización no radicada enviado.',
            'check-datosgov': 'Correo enviado por problema al consultar datos.gov.co.',
            'expd-no-encontrado': '{} Correo enviado por expediente no encontrado.',
        }
        logger.info(msg[reason].format(rad).strip())


def months() -> tuple:
    """Return the list of months in spanish"""
    return ('', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre',
            'Diciembre')


def pretty_date(dt) -> str:
    """
    Receives a date and return the nex format:
    13 de Febrero del 2023 a las 10:05 AM
    hoy a las 7:44 AM
    ayer a las 2:08 PM
    """
    first_part = when(dt)
    return format(dt, f'{first_part} a las %I:%M %p')


def day_slash_month_year(dt) -> str:
    """
    Return a date with the next format:
        - 13/07/23
    """
    return format(dt, '%d/%m/%y')


def when(dt) -> str:
    """
    Validate the day of the input date and might return the next:
        - 'Ayer'
        - 'Hoy'
        - '%e de Julio'
    """
    today = date.today()
    yesterday = today - timedelta(days=1)
    if today.day == dt.day and today.month == dt.month:
        return 'hoy'
    elif yesterday.day == dt.day and yesterday.month == dt.month:
        return 'ayer'
    else:
        month = months()
        m = dt.month
        return f'el %e de {month[m]}'


dct = {'0': 'X', '1': 'y', '2': 'z', '3': 'N', '4': 'o', '5': 'k',
       '6': 'J', '7': 'C', '8': 'b', '9': 'a'}


def encrypt(num: int) -> str:
    """
    >>> encrypt(875800757559)
    'bckbxxckckka'
    """
    resp = [dct[s] for s in str(num) if s in dct]
    return ''.join(resp)


def decrypt(txt: str) -> str:
    """
    >>> decrypt('bckbxxckckka')
    875800757559
    """
    reverse_dct = {v: k for k, v in dct.items()}
    resp = [reverse_dct[s] for s in txt if s in reverse_dct]
    return ''.join(resp)


def update_rad_from_fbase(rad: Radicacion, resp_fbase: dict) -> None:
    """Actualiza un radicado con base en resp_fbase"""
    logger.info(f"{rad.numero_radicado} siendo actualizado con información de Firebase.")
    if not rad.acta_entrega:
        rad.acta_entrega = str(resp_fbase['act'])
    rad.domiciliario_nombre = resp_fbase['nomDomi']
    rad.domiciliario_ide = resp_fbase['docDomi']
    rad.despachado = datetime.strptime(
        f"{resp_fbase['deliveryDate']} {resp_fbase['deliveryHour']}",
        '%Y/%m/%d %H:%M:%S'
    )
    rad.domiciliario_empresa = resp_fbase['empDomi']
    rad.estado = resp_fbase['state']
    rad.factura = resp_fbase['invoice']



