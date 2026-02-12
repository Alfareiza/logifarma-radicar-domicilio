import json
import os
import pickle
from datetime import datetime, timedelta
from typing import Tuple, Dict

import requests
from decouple import config
from django.template.loader import get_template
# from pymssql import Connection
from requests import Timeout
from urllib3.exceptions import NewConnectionError, MaxRetryError

from core.apps.base.resources.decorators import hash_dict, logtime, \
    timed_lru_cache
from core.apps.base.resources.email_helpers import get_complement_subject
from core.apps.base.resources.mutual_ser import MutualSerAPI
from core.apps.base.resources.sap import SAP
from core.apps.base.resources.tools import notify
from core.settings import BASE_DIR, NSCRIPTIOD_HTTP, NSCRIPTIOD_HTTPS
from core.settings import logger

pickle_path = BASE_DIR / "core/apps/base/resources/stored.pickle"


def call_api_eps(url: str, payload: dict) -> dict:
    headers = {'Content-Type': 'text/plain'}
    return request_api(url, headers, payload)


def update_status_factura_cajacopi(factura: str, valor_factura: int, num_aut: str) -> dict:
    """
    Cambia el estado de una factura.
    Incialmente llamado desde core.apps.tasks.utils.pipeline.Send2Cajacopi.cajacopi_calls.
    :param factura: Valor que representa la factura de una autorización.
    :param valor_factura: Valor total de una factura.
    :param num_aut: Número de autorización.
    :return: Respuesta de la api de Cajacopi:
            Ej.:
                - {}
                - {"codigo": "1", "mensaje": "Error!. La autorizacion no tiene detalles. AutProCode:2083"}
    """
    url = "https://genesis.cajacopieps.com/api/api_qr.php"
    payload = {
        "function": "p_inserta_factura_aut",
        "factura": factura,
        "valorFactura": valor_factura,
        "autorizacion": num_aut
    }
    headers = {'Content-Type': 'text/plain'}
    return request_api(url, headers, payload)


@logtime('API')
def auth_api_medicar():
    """
    Hace un llamado a la API de Medicar para obtener el token y
    guarda la información en el pickle_path.pickle.
    :return: token: Token generado a través de la api
    """
    url = "https://medicarws.sis-colombia.com/api/auth/login?" \
          f"email={config('EMAIL_API_MEDICAR')}&" \
          f"password={config('PWD_API_MEDICAR')}"

    headers = {'Content-Type': 'text/plain'}
    try:
        if response := requests.request("POST", url, headers=headers):
            result = json.loads(response.text.encode('utf8'))
            with open(pickle_path, 'wb') as f:
                time_to_req = datetime.now() + timedelta(seconds=result['expires_in'] - 60)
                pickle.dump([result["access_token"], time_to_req], f)

            return result["access_token"]
        else:
            logger.warning(f'Error solicitando autorización'
                           f' API MEDICAR: {response.text}')
    except Exception as e:
        logger.error('Error llamando API de medicar: ', e)

def detect_ip(proxies=None):
    """Make a call to a server in order to determine which is the IP calling there."""
    if proxies is None:
        proxies = {}
    ip = 'unknown'
    try:
        res = requests.request('GET', 'https://httpbin.org/ip', proxies=proxies)
        ip = json.loads(res.text.encode('utf8')).get('origin')
    except Exception as e:
        logger.warning(f"No se pudo capturar IP por error {str(e)}")
    return ip

@hash_dict
@logtime('API')
@timed_lru_cache(300)
def request_api(url, headers, payload, method='POST') -> dict:
    complement_subject = get_complement_subject(payload)
    payload = json.dumps(payload)
    # logger.info(f'API Llamando [{method}]: {url}')
    # logger.info(f'API Header: {headers}')
    # logger.info(f'API Payload: {payload}')
    # proxs = {"http": NSCRIPTIOD_HTTP, "https": NSCRIPTIOD_HTTPS} if 'cajacopi' in url else {}
    ip = detect_ip()
    try:
        logger.info(f'API Llamando [{method}]: {url} desde {ip}')
        response = requests.request(method, url, headers=headers, data=payload, timeout=10, proxies={})
        if response.status_code == 200:
            return json.loads(response.text.encode('utf-8'), strict=False)
        if response.status_code != 429:
            notify('error-api', f'ERROR EN API {complement_subject}',
                   f"STATUS CODE: {response.status_code}\n\n"
                   f"IP: {locals().get('ip', 'unknown')}\n\n"
                   f"URL: {url}\n\nHeader: {headers}\n\n"
                   f"Payload: {payload}\n\n{response.text}")
        return {'error': 'No se han encontrado registros.', 'codigo': '1'}
    except Timeout as e:
        ip_safe = locals().get('ip', 'unknown')
        notify('error-api', f'ERROR TIMEOUT EN API {complement_subject}',
               f"ERROR: {e}.\nNo hubo respuesta de la API en 10 segundos desde ip {ip_safe}")
        return {}
    except requests.exceptions.SSLError as e:
        notify('error-api', f'ERROR SSL en API {complement_subject}',
               f"ERROR: {e}")
        return {}
    except NewConnectionError as e:
        notify('error-api', f'ERROR NewConnectionError en API {complement_subject}',
               f"ERROR: {e}")
        return {}
    except MaxRetryError as e:
        notify('error-api', f'ERROR MaxRetryError en API {complement_subject}',
               f"ERROR: {e}")
        return {}
    except Exception as e:
        notify('error-api', f'ERROR EN API {complement_subject}',
               f"ERROR: {e}\n\nRESPUESTA DE API: response de {method} no capturado sobre url {url!r}")
        return {}


def call_api_medicar(payload: dict, endpoint: str):
    """
    Consulta la API de medicar a partir de un payload y endpoint.
    :param payload: Puede ser:
                        - {"nit_eps": "901543211", "autorizacion": "123456"}
                        - {"Centro": "920"}, "list-inventory/client/6"
    :param endpoint: Puede ser:
                        - 'logifarma/obtenerDatosFormula'
                        - 'list-inventory/client/6'
    :return: - En caso de consultar los datos de una formula, retornará un
               diccionário con la información de la formula.
             - En caso de consultar el inventario, retornaraá una lista con
               diccionarios donde cada uno es un articulo.
    """
    call_auth = should_i_call_auth()
    token = auth_api_medicar() if call_auth is True else call_auth
    url = f"https://medicarws.sis-colombia.com/api/{endpoint}"
    headers = {'Authorization': f'Bearer {token}',
               'Content-Type': 'application/json'}
    resp = request_api(url, headers, payload)
    return resp


def obtener_datos_identificacion_fomag(tipo: str, value: str) -> dict:
    """
    Llama API de SAP y consulta datos referentes a afiliado de Fomag.
    Ejemplo de respuesta:
            - En caso de haber registros:
             {'NOMBRE': 'MOISES AGUILA DELFIN',
             'PRIMER_NOMBRE': 'MOISES',
             'PRIMER_APELLIDO': 'AGUILA'}
            - En caso de no encontrarse registros:
              {}

    """
    sap = SAP()
    resp = sap.get_info_afiliado(tipo, value)

    def parse_response(resp_api: dict) -> dict:
        retval = {'NOMBRE': 'no existe'}

        data_user = value[0] if (value := resp_api.get('value')) else None
        if data_user:
            retval |= {
                'NOMBRE': f"{data_user.get('U_LF_Primer_Nom')} {data_user.get('U_LF_Primer_Ape')} {data_user.get('U_LF_Segundo_Ape')}",
                'PRIMER_NOMBRE': data_user.get('U_LF_Primer_Nom'),
                'PRIMER_APELLIDO': data_user.get('U_LF_Primer_Ape')
            }
        return retval

    return parse_response(resp)


def obtener_datos_identificacion_mutual_ser(tipo: str, value: str) -> dict:
    """
    Llama API de Mutual Ser y consulta datos referentes a afiliado de Mutual Ser.
    Ejemplo de respuesta:
            - En caso de haber registros:
             {'NOMBRE': 'MOISES AGUILA DELFIN',
             'PRIMER_NOMBRE': 'MOISES',
             'PRIMER_APELLIDO': 'AGUILA',
             'STATUS': 'ACTIVO'}
            - En caso de no encontrarse registros o haber error en la respuesta:
              {}

    """
    ms = MutualSerAPI()
    return ms.get_info_afiliado(tipo, value)


def should_i_call_auth():
    """
    Verifica si debe ser solicitado un nuevo
    token a la api de medicar.
    :return: True or token
    """
    if not pickle_path.exists():
        return True

    with open(pickle_path, 'rb') as f:
        token, time_to_req = pickle.load(f)
        if not token or token and datetime.now() > time_to_req:
            return True
        else:
            return token


@logtime('FIREBASE')
def get_firebase_acta(acta: int) -> dict:
    """
    Consulta información en firebase con base al número de acta
    :param acta: 123456
    :return: Una vez consultada la url
            Si el status_code != 200:
             :return {}
            Si no hubo respuesta en 20 segundos:
             :return {}
            Si el status_code == 200:
                Si el response.text == null
                    :return {'state': 'null'}
                Si no:
                    :return
                      {"act":"123456", "actFileId": "1Z654-I_Hla",
                      "address": "CRA 9 88 88", "affiliateDoc": "1143000000",
                      "afiliateName": "JANE DOE FOO BAR",
                      "authorizationNumber": "8758000000",
                      "city": "SOLEDAD", "deliveryDate": "2023/3/29",
                      "deliveryHour": "11:34:24", "departament": "ATL",
                      "docDomi": "ID11430000045", "empDomi": "Nombre Empresa",
                      "haveInvoiceDocument": true, "invoice": "LGF456123",
                      "item": 3, "mipres": "0", "neighborhood": "SOLEDAD 2000",
                      "nomDomi": "Jane Jane Jane", "phone1": "3160000000",
                      "phone2": "", "state": "Completed"}
    """
    try:
        response = requests.request('GET',
                                    f"{config('FBASE_DATABASEURL')}/completed_deliveries/{acta}.json",
                                    timeout=20
                                    )
        if response.status_code != 200:
            raise Exception(response.text)
        if response.text == 'null':
            return {'state': 'null'}
        else:
            return json.loads(response.text.encode('utf-8'), strict=False)
    except Timeout as e:
        notify('error-api', f'ERROR CONSULTANDO FIREBASE - Acta #{acta}',
               f"ERROR: {e}.\nNo hubo respuesta de FIREBASE en 20 segundos")
        return {}
    except Exception as e:
        notify('error-api', f'ERROR CONSULTANDO FIREBASE - Acta #{acta}',
               f"ERROR: {e}\n\nRESPUESTA DE API: {response.text}")
        return {}


def check_meds(info_email: dict):
    """
    Revisa el CUM de cada medicamento y si no lo encuentra en la página
    web de la función check_med, entonces envía un correo.
    :param info_email:
           Ex.:
               {
                  'AFILIADO': 'GUTIERREZ TEIXEIRA JACKSON WOH',
                 'ARCHIVO': 'https://address.eps.com/temp/14429d7a96171a.pdf',
                 'CELULAR': '3103095613',
                 'CORREO': 'something@gmail.com',
                 'CORREO_RESP_AUT': 'something@eps.com',
                 'CORREO_RESP_GUARDA': 'something@gmail.com',
                 'DETALLE_AUTORIZACION': [{'CANTIDAD': '30',
                                           'CUMS': '15875-1',
                                           'NOMBRE_PRODUCTO': 'TRIMEBUTINA MALEATO 200MG '
                                                              'TABLETA RECUBIERTA'}],
                 'DIAGNOSTICO': 'R102-DOLOR PELVICO Y PERINEAL',
                 'DIRECCION': 'CL 6C 1 41',
                 'DOCUMENTO_ID': '12340316',
                 'ESTADO_AFILIADO': 'ACTIVO',
                 'ESTADO_AUTORIZACION': 'PROCESADA',
                 'FECHA_AUTORIZACION': '10/04/2023',
                 'IPS_SOLICITA': 'FUNDACION CLINICA MATERNO INFANTIL ADELA DE CHAR',
                 'MEDICO_TRATANTE': 'FRANK LAMPARD',
                 'MIPRES': '0',
                 'NUMERO_AUTORIZACION': 8758007512345,
                 'Observacion': 'UNICA ENTREGA Y DE LA HOZ',
                 'P_APELLIDO': 'GUTIERREZ',
                 'P_NOMBRE': 'JACKSON',
                 'REGIMEN': 'CONTRIBUTIVO',
                 'RESPONSABLE_AUT': 'ZUCKEBERG GARCIA CARLOS ELIAS',
                 'RESPONSABLE_GUARDA': 'CARMELO BARBOSA GATES',
                 'SEDE_AFILIADO': 'SOLEDAD',
                 'S_APELLIDO': 'TEIXEIRA',
                 'S_NOMBRE': 'WOH',
                 'TELEFONO': '',
                 'TIPO_IDENTIFICACION': 'CC',
                 'barrio': 'El Recreo',
                 'celular': 3111231234,
                 'direccion': 'Karrera 3sur#7A-17',
                 'email': [''],
                 'municipio': <Municipio: Barranquilla, Atlántico>,
                 'whatsapp': None
                 }
    :return: None
    """
    meds = info_email['DETALLE_AUTORIZACION']
    htmly = get_template(BASE_DIR / "core/apps/base/templates/notifiers/cum_no_encontrado.html")

    for med in meds:
        # expediente = med['CUMS'].split('-')[0]
        res = check_med_bd(med['CUMS'])
        if not res:
            info_email.update(cum=med['CUMS'], desc=med['NOMBRE_PRODUCTO'])
            html_content = htmly.render(info_email)
            notify(
                "expd-no-encontrado",
                f"No existe código CUM {med['CUMS']} en BD",
                html_content,
                to=['logistica@logifarma.co'],
                bcc=['alfareiza@gmail.com']
            )

# Deprecated 05-Oct-2023
# def check_med(med: str) -> list:
#     """
#     Consulta el expediente de un medicamento y retorna la respuesta.
#     :param med: 20110698
#     :return: Si existe, retorna una lista con al menos un dicionário
#              Sino, una lista vacía.
#     """
#     try:
#         url = f"https://www.datos.gov.co/resource/i7cb-raxc.json?expediente={med}"
#         response = requests.request('GET', url)
#         if response.status_code != 200:
#             raise Exception(response.text)
#         else:
#             return json.loads(response.text.encode('utf-8'), strict=False)
#     except Timeout as e:
#         notify('check-datosgov', f'ERROR CONSULTANDO EXPEDIENTE {med}',
#                f"ERROR: {e}.\nNo hubo respuesta de datos.gov.co")
#         return []
#     except Exception as e:
#         notify('check-datosgov', f'ERROR CONSULTANDO EXPEDIENTE #c{med}',
#                f"URL: {url}\nERROR: {e}\n\nNo se pudo procesar la respuesta de"
#                f" datos.gov.co: {response.text}")
#         return []


def check_med_bd(codcum: str):
    try:
        conn = make_dbconn()
        cursor = conn.cursor()
        logger.info(f'Buscando expediente {codcum} en base de datos.')
        cursor.execute("SELECT codcum_exp as codcum FROM Logifarma2.dbo.articulos01 "
                       f"WHERE codcum = '{codcum}'")
        cursor.fetchall()
    except Exception as exc:
        logger.error(f"Error al consultar expediente {codcum}: {exc}")
    else:
        return bool(cursor.rowcount)
    finally:
        cursor.close()
        conn.close()


def find_cums(articulos: Tuple) -> Dict[str, str]:
    """
    Busca en base de datos todos los articulos con
    base en el codigo de barra, trayendo su cum.
    :param articulos: Codigos de barras de articulos
                 Ej.: ('123', '456', '789')
    :return: Respuesta de la consulta a base de datos:
             Ej.:
              { '9002260013616': '',
                '9002260016846': '19984812',
                '33425453456': '0'
                '76465727645': '123\t'
                '987654321324': 'N/A',
                '9867543211': 'NA'
                '8904159614847' :'20074902'
              ]
    """
    try:
        conn = make_dbconn()
        cursor = conn.cursor()
        cursor.execute("SELECT LTRIM(RTRIM(codigo)) as barra, "
                       "LTRIM(RTRIM(codcum)) as cum FROM Logifarma2.dbo.articulos01 "
                       f"WHERE codigo IN {articulos}")
        res = cursor.fetchall()
    except Exception as exc:
        logger.error(f"Error al buscar los cums de articulos. {exc}")
    else:
        if not res:
            return {}
        return dict(res)
    finally:
        cursor.close()
        conn.close()


def make_dbconn():
    import pymssql
    server = config('SQL_SERVER_HOST')
    database = config('SQL_SERVER_DB')
    username = config('SQL_SERVER_USER')
    password = config('SQL_SERVER_PASS')
    return pymssql.connect(server=server, database=database,
                           user=username, password=password)


if __name__ == '__main__':
    ...
    # print(call_api_eps(1))
