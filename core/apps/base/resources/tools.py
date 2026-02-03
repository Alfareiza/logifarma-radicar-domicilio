import logging
import pickle
import unicodedata
from datetime import date, datetime, timedelta
from typing import Tuple, Any

from decouple import config
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.core.mail import EmailMessage, get_connection
from django.utils.safestring import SafeString
from pytz import timezone

from core.settings import BASE_DIR, logger, logger as log


def has_accent(word: str) -> bool:
    """Determines if a word has accent
    >>> has_accent('a@a.com')
    False
    >>> has_accent('jane@doe.com')
    False
    >>> has_accent('a@456.com')
    False
    """
    username = word.split('@')[0]
    if not username:
        return True
    for char in username:
        if unicodedata.combining(char) != 0:
            return True
    return False


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


# Deprecated 05-Oct-2023
# def download_file(download_url, filename):
#     """
#     Download a file into the tmp/ folder of the project
#     with the name of the autorization. Ex.: 857300123456789.pdf
#     :param download_url: "https://genesis.cajacopieps.com/temp/XYd1112120fb6a.pdf"
#     :param filename: 857300123456789
#     :return:
#     """
#     try:
#         Path(settings.MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
#         filepath = settings.MEDIA_ROOT / f"{filename}.pdf"
#         response = urllib.request.urlopen(download_url)
#         with open(filepath, 'wb') as file:
#             file.write(response.read())
#     except Exception as e:
#         logger.error('Error descargando archivo:', e)
#         return ''
#     else:
#         return filepath


def clean_ip(ip):
    """
    En algunas ocaciones pueden venir dos ips.
    Así que esta función garantiza que se usará
    una sola
    :param ip: Valor capturado desde el request.
            Ex.: '192.168.0.122', o '192.168.0.122, 144.122.4.51'
    :return:
    """
    ip = ip.split(',')
    return ip[0]


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
    from core.apps.base.models import Radicacion, Barrio
    rad = kwargs.get('NUMERO_AUTORIZACION', None)
    convenio = kwargs.get('CONVENIO', None)

    if kwargs['MEDICAMENTO_AUTORIZADO'] and Radicacion.objects.filter(numero_radicado=str(rad),
                                                                      convenio=convenio).exists():
        logger.warning(f"{rad} Número de radicación ya existe!.")
        return
    municipio = kwargs['municipio']
    if kwargs['MEDICAMENTO_AUTORIZADO']:
        logger.info(f"{rad} Guardando radicación (medicamento autorizado) de {convenio}.")
    else:
        logger.info(
            f"Guardando radicación (medicamento NO autorizado) de {kwargs['DOCUMENTO_ID']} {kwargs['CONVENIO']}.")
    try:
        rad = Radicacion(
            numero_radicado=str(rad),
            convenio=convenio,
            municipio=municipio,
            barrio=Barrio.objects.filter(
                municipio__name__iexact=municipio.name.lower(),
                status='1',
            ).get(name=kwargs.get('barrio', None).lower()),
            cel_uno=kwargs['celular'],
            cel_uno_validado=kwargs.get('celular_validado', False),
            cel_dos=kwargs.get('whatsapp', None),
            email=', '.join(kwargs['email']),
            direccion=kwargs['direccion'],
            ip=kwargs['IP'],
            paciente_nombre=kwargs['AFILIADO'],
            paciente_cc=kwargs['DOCUMENTO_ID'],
            paciente_data=kwargs.get('PACIENTE_DATA'))
        save_in_bd('default', rad)
    except MultipleObjectsReturned as e:
        if "more than one Barrio" in str(e):
            barrios = Barrio.objects.filter(municipio__name__iexact=municipio.name.lower(), status='1').values_list(
                'id', 'name')
            body_content = '\n- '.join([f"{_id} - {name}" for _id, name in barrios])
            notify('error-bd',
                   f"ERROR GUARDANDO RADICACION {rad} EN BASE DE DATOS",
                   f"Barrio {kwargs.get('barrio', '')!r} repetido en municipio {municipio.name.title()}:"
                   f" \n{body_content}\nAsegúrate de borrar el barrio que no tenga radicados")
            logger.error(
                f"{kwargs.get('NUMERO_AUTORIZACION')} Error guardando radicación por barrio {kwargs.get('barrio', '')!r} repetido en {municipio.name.title()}")
    except Exception as e:
        logger.error(f"{kwargs.get('NUMERO_AUTORIZACION')} Error guardando radicación: {str(e)}")
        notify('error-bd',
               f"ERROR GUARDANDO RADICACION {rad} EN BASE DE DATOS", str(e))
    else:
        return rad


def save_in_bd(name_bd: str, rad):
    """
    Guarda una instancia de Radicacion en la base de datos informada en name_bd
    :param name_bd: Puede ser 'default' que son las bases configuradas en settings.
    :return:
    """
    try:
        rad.save(using=name_bd)
    except Exception as e:
        logger.error(e)
        raise Exception(f"No fue posible guardar radicado {rad} en {name_bd}, error={e}") from e
    else:
        logger.info(f"{rad.numero_radicado} Radicación guardada con éxito {rad.id=}")


def discover_rad(body) -> str:
    """
    Busca el radicado en el cuerpo del correo.
    :param body:
    :return: # de radicado
    >>> discover_rad("ERROR ENVIANDO EMAIL- Radicado #2318901402756 CC123234")
    '2318901402756'
    """
    import re
    if isinstance(body, (str, SafeString)):
        if expr := re.findall("\d{9}\d+", body):
            return expr[0]
    return ''


def make_email(subject: str, body: str, to=None, bcc: list = []) -> EmailMessage:
    """
    Crea un objeto EmailMessage a partir de los campos recebidos.
    :param subject: Asunto del correo
    :param body: Cuerpo del Correo
    :param to: Para quien será enviado el correo.
    :param bcc: Copia oculta.
    :return: EmailMessage
    """
    if to is None:
        to = ['alfareiza@gmail.com', 'logistica@logifarma.co']

    connection = get_connection(
        username=config('EMAIL_LOG_USER'),
        password=config('EMAIL_LOG_PASSWORD'),
        fail_silently=False,
    )
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=f"Logs Logifarma <{settings.EMAIL_HOST_USER}>",
        to=to,
        bcc=bcc,
        connection=connection
    )

    from django.utils.safestring import SafeString
    if isinstance(body, SafeString):
        email.content_subtype = "html"

    return email


def notify(reason: str, subject: str, body: str, to=None, bcc: list = []):
    """
    Envía un correo notificando algo.
    :param to: Para quien será enviado el correo.
    :param bcc: Copia oculta.
    :param reason: Puede ser:
                    'error-bd'
                    'error-api'
                    'error-archivo'
                    'error-archivo-url'
                    'error-email'
                    'check-acta'
                    'check-aut'
    :param subject: Asunto del correo
    :param body: Cuerpo del Correo
    :return: Nada
    """
    email = make_email(subject, body, to, bcc)

    rad = discover_rad(email.body) or discover_rad(email.subject)

    try:
        if sent := email.send(fail_silently=False):
            msg = {
                'error-bd': '{} Correo enviado notificando problema al guardar en BD.',
                'error-api': '{} Correo enviado notificando problema con API.',
                'error-archivo-url': 'Correo enviado notificando radicado sin archivo.',
                'error-email': '{} Correo enviado notificando problema al enviar e-mail de confirmación.',
                'error-archivo': 'Correo enviado notificando problema con archivo.',
                'check-acta': 'Correo enviado con reporte de chequeo de actas.',
                'check-aut': '{} Correo de alerta de autorización no radicada enviado.',
                'check-datosgov': 'Correo enviado por problema al consultar datos.gov.co.',
                'expd-no-encontrado': '{} Correo enviado por expediente no encontrado.',
                'med-control': '{} Correo enviado por medicamento controlado.',
                'task-fill-data': '{} Correo enviado por facturas no procesadas en rutina.',
            }
    except Exception as e:
        logger.error(f"{rad} Correo de {reason} no fue enviado. Error: {e}")
    else:
        logger.warning(msg[reason].format(rad).strip())


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


def moment():
    return datetime.now(tz=timezone('America/Bogota'))


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


def update_rad_from_fbase(rad, resp_fbase: dict) -> None:
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
    rad.save()


def update_field(rad, attr, value) -> None:
    if hasattr(rad, attr):
        setattr(rad, attr, value)
        rad.save()
    else:
        logger.error(f'No fue posible actualizar radicación # {rad!r} en bd')


def dt_str_to_date_obj(dt: str) -> datetime.date:
    """
    Convierte una fecha de string a un objeto datetime.date.
    :param dt: Fecha en formato yyyy-mm-dd. Ej.: '2025-06-30'
    :return:
    """
    try:
        return date.fromisoformat(dt)
    except ValueError:
        return date.fromisoformat('2050-12-31')


def datetime_id():
    """
    Crea un numero único basado en el timestamp
    :return:
    """
    last_datetime_id = None
    prev_datetime_ids = set()
    result = int(datetime.now().timestamp() * 1000000)
    num_try = 0
    while result in prev_datetime_ids and num_try < 10:
        result = int(datetime.now().timestamp() * 1000000)
        num_try += 1

    if num_try >= 10:
        result = last_datetime_id + 1

    prev_datetime_ids.add(result)
    last_datetime_id = result

    return str(result)


def login_check(obj) -> bool:
    """
    1. Valida que exista el archivo de login:
        1.1 Caso exista:
                1.1.1 Valida que que la hora de sesión
                        no sea mayor que la hora actual.
                1.1.2 Caso sea mayor, efectua el login.
        1.2 Caso no exista, efectua el login.
    Puede retornar False cuando la API que logra el login este caída.
    :param obj: Instancia de SAPData o MutualSerAPI o cualquier instancia que su clase tenga la función login
    :return: True o False caso haga login o no.
    """
    login_pkl = obj.LOGIN_CACHE
    name_obj = obj.__class__.__name__

    if not login_pkl.exists():
        # log.info(f'[{name_obj}] Cache de login no encontrado')
        login_succeed = obj.login()
    else:
        with open(login_pkl, 'rb') as f:
            sess_id, sess_timeout = pickle.load(f)
            now = moment()
            if now > sess_timeout:
                # log.warning(f'[{name_obj}] Tiempo de login anterior expiró')
                login_succeed = obj.login()
            else:
                # log.info(f"[{name_obj}] Usando login que está en cache")
                obj.sess_id = sess_id
                login_succeed = True
    return login_succeed


def add_user_id_to_formatter(handler, user_id):
    old_formatter = handler.formatter

    new_defaults = {"ssid": getattr(old_formatter, "_my_ssid", ''), "user_id": user_id}
    new_fmt_str = "%(asctime)s %(levelname)s [%(ssid)s|%(user_id)s] %(message)s"
    updated_formatter = logging.Formatter(
        new_fmt_str,
        old_formatter.datefmt,
        defaults=new_defaults
    )
    handler.setFormatter(updated_formatter)
