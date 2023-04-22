import json
import pickle
from datetime import datetime, timedelta

import requests
from decouple import config
from django.template.loader import get_template
from requests import Timeout

from core.apps.base.resources.decorators import hash_dict, logtime, \
    timed_lru_cache
from core.apps.base.resources.tools import notify
from core.settings import BASE_DIR
from core.settings import logger

pickle_path = BASE_DIR / "core/apps/base/resources/stored.pickle"


def call_api_eps(num_aut: int) -> dict:
    """
    Solicita información del numero de la autorización a la API de la EPS.
    :param num_aut: Número de autorización digitado por el usuario en el front.
                Ej: 875800731698
    :return: Dict
            Ej: En caso de no tener datos
            { "codigo":"1","mensaje":"Datos no encontrados!2" }
            Ej: En caso de tener datos
            {
                "TIPO_IDENTIFICACION": "CC",
                "DOCUMENTO_ID": "14988099",
                "AFILIADO": "COLLAZOS ROJAS GUILLERMO ",
                "P_NOMBRE":"PEDRO","S_NOMBRE":"MANUEL",
                "P_APELLIDO":"PACHECO","S_APELLIDO":"EFROS",
                "ESTADO_AFILIADO": "ACTIVO",
                "SEDE_AFILIADO": "SOLEDAD",
                "REGIMEN": "SUBSIDIADO",
                "DIRECCION": "CRA 30 NO 56 - 30",
                "CORREO": "",
                "TELEFONO": "",
                "CELULAR": "3022458917",
                "ESTADO_AUTORIZACION": "PROCESADA",
                "FECHA_AUTORIZACION": "11/11/2022",
                "MEDICO_TRATANTE": "omar valle",
                "MIPRES": "0",
                "DIAGNOSTICO": "I10X-HIPERTENSION ESENCIAL (PRIMARIA)",
                "ARCHIVO": "https://genesis.cajacopieps.com/temp/63dcxy1234560fa.pdf",
                "DETALLE_AUTORIZACION": [
                    {
                        "CUMS": "20059406-1",
                        "NOMBRE_PRODUCTO": "FOSFOMICINA 3GR POLVO PARA RECONSTRUIR",
                        "CANTIDAD": "4"
                    },
                    {
                        "CUMS": "19938870-7",
                        "NOMBRE_PRODUCTO": "ACIDO FOLICO 1MG + HIERRO 100MG TABLETA RECUBIERTA",
                        "CANTIDAD": "30"
                    }
                ]
            }
    """
    url = "https://genesis.cajacopieps.com/api/api_qr.php"
    payload = {"function": "p_mostrar_autorizacion",
               "serial": str(num_aut),
               "nit": "900073223"}
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


@hash_dict
@logtime('API')
@timed_lru_cache(300)
def request_api(url, headers, payload, method='POST'):
    num_aut = payload.get('autorizacion') or payload.get('serial')
    payload = json.dumps(payload)
    # logger.info(f'API Llamando [{method}]: {url}')
    # logger.info(f'API Header: {headers}')
    # logger.info(f'API Payload: {payload}')
    try:
        response = requests.request(method, url, headers=headers, data=payload, timeout=20)
        # logger.info(f'API Response [{response.status_code}]: {response.text}')
        if response.status_code != 200:
            res = requests.request('GET', 'https://httpbin.org/ip')
            ip = json.loads(res.text.encode('utf8'))
            notify('error-api', f'ERROR EN API - Radicado #{num_aut}',
                   f"STATUS CODE: {response.status_code}\n\n"
                   f"IP: {ip.get('origin')}\n\n"
                   f"URL: {url}\n\nHeader: {headers}\n\n"
                   f"Payload: {payload}\n\n{response.text}")
            return {'error': 'No se han encontrado registros.', 'codigo': '1'}
        else:
            return json.loads(response.text.encode('utf-8'), strict=False)
    except Timeout as e:
        notify('error-api', f'ERROR EN API - Radicado #{num_aut}',
               f"ERROR: {e}.\nNo hubo respuesta de la API en 20 segundos")
        return {}
    except Exception as e:
        notify('error-api', f'ERROR EN API - Radicado #{num_aut}',
               f"ERROR: {e}\n\nRESPUESTA DE API: {response.text}")
        return {}


def call_api_medicar(num_aut: int) -> dict:
    """
    Recibe el número de autorización que aparece en los pedidos de los usuarios.
    Realiza el llamado a la API y retorna un diccionario con la respuesta.
    :param num_aut:
    :return: Dict:
            Ej: En caso de haber un error
                {}
            Ej: En caso de no haber encontrado registros
                { "error": "No se han encontrado registros."}
            Ej: En caso de enviar el nit incorrecto
                { "error": "El Nit ingresado no corresponde a ningun convenio."}
            Ej: En caso de haber encontrado registros
                {
                    "ssc": 2640835,
                    "autorizacion": "875800731698",
                    "factura": null,
                    "fecha_de_factura": null,
                    "hora_de_factura": null,
                    "resolucion_de_factura": null,
                    "codigo_centro_factura": "920",
                    "nombre_centro_factura": "Central Domicilios Barranquilla (920)",
                    "direccion_centro_factura": "VIA 40 No. 69 - 58 Bodega D5 Parque \r\nIndustrial VIA 40",
                    "usuario_dispensa": "Silva Jose Thiago Camargo",
                    "nombre_eps": "CAJA DE COMPENSACION FAMILIAR CAJACOPI ATLANTICO",
                    "nit_eps": "890102044",
                    "plan": "REGIMEN SUBSIDIADO",
                    "direccion_eps": "Calle 4 No 4 – 5",
                    "nombre_afiliado": "GUTIERREZ TEIXEIRA JACKSON WOH",
                    "tipo_documento_afiliado": "CC",
                    "documento_afiliado": "12340316",
                    "nivel": "6",
                    "mipres": null,
                    "id_mipres": null,
                    "nombre_medico": "FRANK LAMPARD",
                    "nombre_ips": "Hospital De Leticia Materno Infantil",
                    "articulos": [
                        {
                            "codigo_barras": "7707184601001",
                            "cum": "20089927-1",
                            "atc": "J01XX01",
                            "descripcion": "FOSFOMICINA 3G POL ORL C*1 SOB X 8G (LESGENA) - CLOSTER PHARMA",
                            "cantidad": 0,
                            "costo_promedio": 0,
                            "precio_venta": null,
                            "iva": 0
                        },
                        {
                            "codigo_barras": "7703454121620",
                            "cum": "19982964-5",
                            "atc": "B03AE02",
                            "descripcion": "HERREX FOL 1000 X 30  TABLETAS",
                            "cantidad": 0,
                            "costo_promedio": 0,
                            "precio_venta": null,
                            "iva": 0
                        }
                    ]
                }
    """
    call_auth = should_i_call_auth()
    token = auth_api_medicar() if call_auth is True else call_auth
    url = "https://medicarws.sis-colombia.com/api/logifarma/obtenerDatosFormula"
    headers = {'Authorization': f'Bearer {token}',
               'Content-Type': 'application/json'}
    payload = {"nit_eps": "901543211", "autorizacion": f"{num_aut}"}
    resp = request_api(url, headers, payload)
    try:
        if isinstance(resp, dict) and 'error' in resp.keys():
            if resp.get('error') == 'No se han encontrado registros.':
                return resp
            elif resp.get('error') == 'El Nit ingresado no corresponde a ningun convenio.':
                payload['nit_eps'] = '890102044'
                resp = request_api(url, headers, payload)
        return resp[0]
    except KeyError:
        # msg = f"{resp}"
        logger.error('Al consultarse hubo una respuesta inesperada: ', str(resp))
        return {}


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
        expediente = med['CUMS'].split('-')[0]
        res = check_med_bd(expediente)
        if not res:
            info_email.update(expediente=expediente, cum=med['CUMS'], desc=med['NOMBRE_PRODUCTO'])
            html_content = htmly.render(info_email)
            notify(
                "expd-no-encontrado",
                f"No existe código CUM {expediente} en BD",
                html_content,
            )


def check_med(med: str) -> list:
    """
    Consulta el expediente de un medicamento y retorna la respuesta.
    :param med: 20110698
    :return: Si existe, retorna una lista con al menos un dicionário
             Sino, una lista vacía.
    """
    try:
        url = f"https://www.datos.gov.co/resource/i7cb-raxc.json?expediente={med}"
        response = requests.request('GET', url)
        if response.status_code != 200:
            raise Exception(response.text)
        else:
            return json.loads(response.text.encode('utf-8'), strict=False)
    except Timeout as e:
        notify('check-datosgov', f'ERROR CONSULTANDO EXPEDIENTE {med}',
               f"ERROR: {e}.\nNo hubo respuesta de datos.gov.co")
        return []
    except Exception as e:
        notify('check-datosgov', f'ERROR CONSULTANDO EXPEDIENTE #c{med}',
               f"URL: {url}\nERROR: {e}\n\nNo se pudo procesar la respuesta de"
               f" datos.gov.co: {response.text}")
        return []

def check_med_bd(codcum: str):
    try:
        import pyodbc
        server = config('SQL_SERVER_HOST')
        database = config('SQL_SERVER_DB')
        username = config('SQL_SERVER_USER')
        password = config('SQL_SERVER_PASS')

        cnxn = pyodbc.connect(f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                              f"SERVER='{server}';DATABASE='{database};"
                              f"UID='{username}';PWD='{password}")
        cursor = cnxn.cursor()
        cursor.execute(
            'select codcum_exp as codcum from articulos01 where codcum_exp = ?',
            codcum)

        results = cursor.fetchall()
    except Exception as exc:
        logger.error(f"Error al consultar expediente {codcum}: {exc}")
    else:
        return bool(cursor.rowcount)

if __name__ == '__main__':
    ...
    # print(call_api_eps(1))
