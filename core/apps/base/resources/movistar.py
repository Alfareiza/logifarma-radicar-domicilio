import json

import requests
from decouple import config
from requests import Timeout, HTTPError

from core.settings import logger


class ApiMovistar:

    def __init__(self):
        self.token = config('TOKEN_MOVISTAR')

    def request_api(self, method, url, payload=None) -> dict:
        if payload is None:
            payload = {}
        try:
            response = requests.request(method, url, headers=self.set_header(),
                                        data=json.dumps(payload),
                                        timeout=10)
            response.raise_for_status()
        except Timeout:
            logger.error(txt := "No hubo respuesta de la API en 10 segundos.")
            res = {"ERROR": f"[MOVISTAR TIMEOUT] {txt}"}
        except HTTPError as e:
            match e.response.status_code:
                case code if code >= 500:
                    msg = f"STATUS_CODE={code} {str(e)}"
                case _:
                    if 'application/json' in e.response.headers['Content-Type']:
                        msg = e.response.json()
                    else:
                        msg = e.response.content
            res = {"ERROR": f"[CONNECTION] {str(msg)}"}
        except ConnectionResetError as e:
            res = {"ERROR": f"[CONNECTION] ConnectionResetError {str(e)}"}
        except Exception as e:
            res = {"ERROR": f"[CONNECTION] {str(e)}"}
        else:
            res = response.json()
        if 'ERROR' in res:
            logger.error(f"[MOVISTAR ERROR] {res}")
        return res

    def set_header(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f"App {self.token}"
        }

    def post(self, url: str, item: dict) -> dict:
        """Realiza el post ante la API de SAP y retorna
        lo que haya resultado de la función request_api"""
        return self.request_api('POST', url, payload=item)

    def get(self, url):
        return self.request_api('GET', url)
