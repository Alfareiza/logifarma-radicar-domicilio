from typing import List, Dict

from core.apps.base.resources.api_calls import call_api_medicar
from core.settings import logger as log


def obtener_datos_formula(num_aut: int) -> dict:
    """
    Recibe el número de autorización que aparece en los pedidos de
    los usuarios, luego el llamado a la API y retorna un diccionário
    con la respuesta.
    :param num_aut: Número de autorización a ser consultada.
               Ej.: 5022600074146
   :return: Diccionário con la respuesta de la API:
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
    resp = call_api_medicar(
        {"nit_eps": "901543211", "autorizacion": f"{num_aut}"},
        'logifarma/obtenerDatosFormula'
    )
    try:
        # if isinstance(resp, dict) and 'error' in resp.keys():
            # if resp.get('error') == 'No se han encontrado registros.':
            #     ...
            #  [⬇︎CÓDIGO OBSOLETO⬇︎] Este nit no es más reconocido por la API de medicar.
            # elif resp.get('error') == 'El Nit ingresado no corresponde a ningun convenio.':
                # resp = call_api_medicar(
                #     {"nit_eps": "890102044", "autorizacion": f"{num_aut}"},
                #     'logifarma/obtenerDatosFormula'
                # )
                # resp = resp[0]
        if isinstance(resp, list) and len(resp) == 1 and 'autorizacion' in resp[0].keys():
            resp = resp[0]
    except KeyError:
        log.error("Al consultarse \'obtenerDatosFormula\' hubo una respuesta inesperada: ", str(resp))
        return {}
    return resp


def obtener_inventario(centro: int) -> List[Dict]:
    """
    Consulta el inventario a partir de un 'Centro'
    :param centro: Número de bodega a ser consultada (centro).
    :return: Lista de diccionaários donde cada uno representa
             un articulo con informacion relacionada a el.
             Se asume que si el artículo se encuentra en la lista
             es porque hay inventario de este.
             Ex.:
                [
                    {
                      'Centro': '920',
                      'CodMol': 38574,
                      'CodBarra': '7702870071502',
                      'Descripcion': 'CAFEINA+NAPROXENO 65MG+550MG C*36 TAB (LUMBAL FORTE)',
                      'Lote': '23A634',
                      'FechaVencimiento': '2025-04-30',
                      'Inventario': 22,
                      'CostoPromedio': 1366,
                      'CantidadEmpaque': 36
                    }
                    ...
                ]
    """
    return call_api_medicar({'Centro': centro}, 'list-inventory/client/6')

