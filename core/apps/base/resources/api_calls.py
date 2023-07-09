import json
import pickle
from datetime import datetime, timedelta
from typing import Dict

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

def call_api_eps_doc(tipo_doc: str, doc: str) -> dict:
    """
    Solicita información según su identificación.
    :param tipo_doc: Tipo de identificación del usuario:
                Ej.: 'CC', 'TI', 'SC', 'AS', 'CE', 'PT', 'RC', 'PE' o 'CN'.
    :param doc:
                Ej.: '12312313', 'T44645645', ...
    :return: En caso de no hacer contacto con la API retorna:
                {}
            En caso de hacer contacto con la API, puede retornar:
            Si documento no existe:
                {
                    "info": {
                        "CODIGO": "0",
                        "NOMBRE": "Datos del Afiliado no encontrado, 
                                   por favor validar nuevamente"
                    },
                    "aut": [],
                    "tipo": "API"
                }
            Si documento existe:
                {
                    "info": {
                        "NombreCompleto": "JANE DOE FOO BAR",
                        "Codigo": 1,
                        "TipoDocumento": "TI",
                        "Documento": "1043933683",
                        "FechaNacimiento": "10/05/2016",
                        "Departamento": "ATLANTICO",
                        "Municipio": "TUBARA",
                        "EdadDias": 1541,
                        "Estado": "ACTIVO",
                        "Regimen": "SUBSIDIADO",
                        "Sexo": "MASCULINO",
                        "Celular1": "3116655713 - ",
                        "email": "notiene@hotmail.com",
                        "SexoCodigo": "M",
                        "CodigoRegimen": "S",
                        "DIRECCION": "CARRERA 1 NO  2 34",
                        "NIVEL": 1,
                        "PORTABILIDAD": "N",
                        "EMPLEADOR": null,
                        "SINIESTRO": "false",
                        "TUTELA": "false",
                        "FECHA_AFILIACION": "05/09/2055",
                        "FECHA_RETIRO": null,
                        "CAMBIO_ESTADO": null,
                        "ALTOCOSTO": "N",
                        "SUPERSALUD": "CajacopiEPS",
                        "AFIC_T045": "N"
                    },
                    "aut": [
                        {
                            "NUMERO": "16718",
                            "UBICACION": "7914",
                            "AUTORIZACION_MANUAL": "791400024211",
                            "SERVICIO": "SERVICIO FARMACEUTICO",
                            "NOMBRE_AFI": "FOO BAR JANE DOE",
                            "FECHA": "01/06/2055",
                            "FECHAORDEN": "04/04/2055",
                            "FECHASOLICITUD": "28/05/2055",
                            "RESPONSABLE": "DONALD TRUMP",
                            "NUM_ESOA": "",
                            "TIPO_DOC": "TI",
                            "DOCUMENTO": "1043933683",
                            "DX": "L80X",
                            "NOM_DX": "VITILIGO",
                            "REGIMEN": "SUBSIDIADO",
                            "TUTELA": "0",
                            "AUTC_CLASE": "PBS",
                            "CONTRATO": "70581",
                            "MIPRES": "0",
                            "CLASIFICACION": "714",
                            "UBICACION_PACIENTE": "Consulta Externa",
                            "NIT": "600043221",
                            "IPS": "LOGIFARMA S.A.S.",
                            "ANTICIPO": "NO",
                            "PROGRAMADA": "NO",
                            "FACTURA": "0",
                            "NUMSPAN": "2",
                            "ESTADO_CLASE": "green",
                            "STATUS": "NORMAL",
                            "MOTIVO_ANULACION": "",
                            "STATUS_CLASE": "green",
                            "ESTADO": "PROCESADA",
                            "DETALLES": [
                                {
                                    "renglon": "1",
                                    "cod_producto": "20111586-1",
                                    "nombre_producto": "TACROLIMUS 0,03G/100G UNGUENTO TOPICO",
                                    "valor": "          $50,130.00",
                                    "total": "50130",
                                    "total_cf": "          $50,130.00",
                                    "cantidad": "1"
                                }
                            ]
                        },
                        {...},
                        {...}
                    ],
                    "tipo": "API"
                }
    """
    url = "https://genesis.cajacopieps.com/api/api_consulta_aut_xdoc.php"
    payload = {"function": "consulta_aut",
               "tipo_doc": tipo_doc,
               "documento": doc,
               "nit": "900073223"}
    headers = {'Content-Type': 'text/plain'}
    return request_api(url, headers, payload)

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
    logger.info(f'API Llamando [{method}]: {url}')
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
    except requests.exceptions.SSLError as e:
        notify('error-api', f'ERROR SSL en API - Radicado #{num_aut}',
               f"ERROR: {e}")
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
        import pymssql
        server = config('SQL_SERVER_HOST')
        database = config('SQL_SERVER_DB')
        username = config('SQL_SERVER_USER')
        password = config('SQL_SERVER_PASS')
        conn = pymssql.connect(server=server, database=database,
                               user=username, password=password)
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

def build_data_from_doc(identificacion: dict, autorizacionServicio: dict) -> Dict:
    """
    Busca cedula en API de Cajacopi y con la respuesta busca la autorización
    ingresada por el usuario. Si la encuentra entonces retorna un diccionário
    con el formato de autorizacionServicio.
    :param identificacion: {'tipo_identificacion': 'CC', 'valor_identificacion': '123456787'}
    :param autorizacionServicio: {'num_autorizacion': {'NUMERO_AUTORIZACION': 123123123}}
    :return:  Caso no haya respuesta de la API:
                {'tipo_doc': 'CC', 'doc': '123456787}
              Si hay respuesta de la API:
                {
                       "TIPO_IDENTIFICACION":"CC",
                       "DOCUMENTO_ID":"32713544",
                       "AFILIADO":"EVERTSZ GARCIA DENIS MARIA",
                       "P_NOMBRE":"", "S_NOMBRE":"", "P_APELLIDO":"", "S_APELLIDO":"",
                       "ESTADO_AFILIADO":"ACTIVO",
                       "SEDE_AFILIADO":"SOLEDAD",
                       "REGIMEN":"SUBSIDIADO",
                       "DIRECCION":"CRA 15B 60B-18",
                       "CORREO":"", "TELEFONO":"", "CELULAR":"",
                       "ESTADO_AUTORIZACION":"PROCESADA",
                       "FECHA_AUTORIZACION":"13/06/2023",
                       "MEDICO_TRATANTE":"", "MIPRES":"0",
                       "DIAGNOSTICO":"HIPERTENSION ESENCIAL (PRIMARIA)",
                       "ARCHIVO":"",
                       "IPS_SOLICITA":"LOGIFARMA S.A.S.",
                       "Observacion":"",
                       "RESPONSABLE_GUARDA":"MENDOZA LORENA",
                       "CORREO_RESP_GUARDA":"", "RESPONSABLE_AUT":"", "CORREO_RESP_AUT":"",
                       "DETALLE_AUTORIZACION":[
                          {
                             "CUMS":"20101182-6",
                             "NOMBRE_PRODUCTO":"EMPAGLIF..INA 1000 MG TABLETA - JARDIANCE DUO",
                             "CANTIDAD":"30"
                          }
                       ]
                    }}
    """
    tipo_doc, doc = identificacion['tipo_identificacion'], identificacion['valor_identificacion']
    resp_eps_doc = call_api_eps_doc(tipo_doc, doc)
    num_aut = autorizacionServicio['num_autorizacion']['NUMERO_AUTORIZACION']
    try:
        data = {'tipo_doc': tipo_doc, 'doc': doc}
        # Busca autorización en resp_eps_doc, si se encuentra entonces retornará la info con
        # la estructura capturado como la del paso autorizacionServicio
        if aut_detalle := list(
                filter(
                    lambda x: x['AUTORIZACION_MANUAL'] == str(num_aut), resp_eps_doc['aut']
                )
        ):
            data = {
                "TIPO_IDENTIFICACION": aut_detalle[0]['TIPO_DOC'],
                "DOCUMENTO_ID": aut_detalle[0]['DOCUMENTO'],
                "AFILIADO": aut_detalle[0]['NOMBRE_AFI'],
                "P_NOMBRE": aut_detalle[0]['NOMBRE_AFI'].title(),
                "S_NOMBRE": "", "P_APELLIDO": "", "S_APELLIDO": "",
                "ESTADO_AFILIADO": resp_eps_doc['info']['Estado'],
                "SEDE_AFILIADO": resp_eps_doc['info']['Municipio'],
                "REGIMEN": resp_eps_doc['info']['Regimen'],
                "DIRECCION": resp_eps_doc['info']['DIRECCION'],
                "CORREO": "", "TELEFONO": "", "CELULAR": "",
                "ESTADO_AUTORIZACION": aut_detalle[0]['ESTADO'],
                "FECHA_AUTORIZACION": aut_detalle[0]['FECHA'],
                "MEDICO_TRATANTE": "",
                "MIPRES": aut_detalle[0]['MIPRES'],
                "DIAGNOSTICO": aut_detalle[0]['NOM_DX'],
                "ARCHIVO": "",
                "IPS_SOLICITA": aut_detalle[0]['IPS'],
                "Observacion": "",
                "RESPONSABLE_GUARDA": aut_detalle[0]['RESPONSABLE'],
                "CORREO_RESP_GUARDA": "", "RESPONSABLE_AUT": "", "CORREO_RESP_AUT": "",
                "DETALLE_AUTORIZACION": []
            }
            for art in aut_detalle[0]['DETALLES']:
                data['DETALLE_AUTORIZACION'].append(
                    {
                        "CUMS": art['cod_producto'],
                        "NOMBRE_PRODUCTO": art['nombre_producto'],
                        "CANTIDAD": art['cantidad']
                    }
                )
        else:
            logger.info(f'Autorización {num_aut} no encontrada asociada a documento {tipo_doc}. {doc}')
    except Exception as e:
        logger.error(f'{num_aut} No fue posible transformar datos de {tipo_doc}. {doc}: {e}')
    finally:
        return data


if __name__ == '__main__':
    ...
    # print(call_api_eps(1))
