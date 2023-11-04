from core.apps.base.resources.api_calls import request_api, call_api_eps


def obtener_datos_autorizacion(num_aut: int) -> dict:
    """
    Solicita información del numero de la autorización a la API de la EPS.
    :param num_aut: Número de autorización digitado por el usuario en el front.
                Ej: 875800731698
    :return: Dict
            Ej: En caso de no tener datos
            { "codigo":"1","mensaje":"Datos no encontrados!2" }
            Ej: En caso de tener datos
            {
                "TIPO_IDENTIFICACION": "TI",
                "DOCUMENTO_ID": "14988331099",
                "AFILIADO": "COLLAZOS ROJAS THIAGO ",
                "P_NOMBRE":"PEDRO","S_NOMBRE":"MANUEL",
                "P_APELLIDO":"PACHECO","S_APELLIDO":"EFROS",
                "ESTADO_AFILIADO": "ACTIVO",
                "SEDE_AFILIADO": "SABANALARGA",
                "REGIMEN": "SUBSIDIADO",
                "DIRECCION": "CRA 55 NO 111 - 30",
                "CORREO": "",
                "TELEFONO": "",
                "CELULAR": "3112458907",
                "ESTADO_AUTORIZACION": "PROCESADA",
                "FECHA_AUTORIZACION": "11/11/2022",
                "MEDICO_TRATANTE": "omar valle",
                "MIPRES": "0",
                "DIAGNOSTICO": "I10X-HIPERTENSION ESENCIAL (PRIMARIA)",
                "ARCHIVO": "https://.../63dcxy1234560fa.pdf",
                "DETALLE_AUTORIZACION": [
                    {
                        "CUMS": "00000-1",
                        "NOMBRE_PRODUCTO": "FOSFOMICINA 3GR",
                        "CANTIDAD": "1"
                    },
                    {
                        "CUMS": "00000-7",
                        "NOMBRE_PRODUCTO": "ACIDO TABLETA RECUBIERTA",
                        "CANTIDAD": "1"
                    }
                ]
            }
        """
    url = "https://genesis.cajacopieps.com/api/api_qr.php"
    payload = {"function": "p_mostrar_autorizacion",
               "serial": str(num_aut),
               "nit": "900073223"}
    return call_api_eps(url, payload)


def obtener_datos_identificacion(tipo: str, value: str) -> dict:
    """
    Obtiene información de un usuario con base en el tipo de identificaión
    y su valor
    :param tipo: Puede ser: CC, TI, RC, CN, CD, PA, PE, PT, SC, CE, MS o AS
    :param value: Valor de identifiación del usuario.
    :return: Respuesta de la api.
             En caso de no existir el usuario:
             {
                "info": {
                    "CODIGO": "0",
                    "NOMBRE": "Datos del Afiliado no encontrado, por favor
                                validar nuevamente"
                },
                "aut": [],
                "tipo": "API"
            }
    """
    url = "https://genesis.cajacopieps.com/php/consultaAfiliados/obtenerafiliadoips.php"
    payload = {"function": "obtenerafiliados",
               "tipodocumento": tipo,
               "documento": value}
    return call_api_eps(url, payload)
