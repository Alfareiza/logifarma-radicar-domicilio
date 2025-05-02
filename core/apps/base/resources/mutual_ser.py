import datetime
import json
import pickle
import re

import requests
from requests import Timeout, HTTPError

from core.apps.base.resources.decorators import login_required
from core.apps.base.resources.tools import moment
from core.settings import BASE_DIR, MS_PASS, MS_USER, MS_API_URL, MS_API_URL_VALIDADOR
from core.settings import logger as log


class MutualSerAPI:
    LOGIN_CACHE = BASE_DIR / 'login_mutual_ser.pickle'

    LOGIN = 'auth/realms/right-validation/protocol/openid-connect/token/'
    VALIDADOR_DERECHOS = 'validateRights/'

    def __init__(self):
        self.sess_id = ''
        self.sess_timeout = None

    def request_api(self, method, url, headers, payload=None) -> dict:
        if payload is None:
            payload = {}
        # sourcery skip: raise-specific-error
        res = {"ERROR": ""}
        timeout = 60
        head_log = '[MUTUAL]'
        try:
            response = requests.request(method, url, headers=headers,
                                        # data=json.dumps(payload),
                                        data=payload,
                                        timeout=timeout)
            response.raise_for_status()
        except Timeout:
            log.error(txt := f"{head_log} No hubo respuesta de la API en {timeout} timeout.")
            res = {"ERROR": f"[TIMEOUT] {txt}"}
        except HTTPError as e:
            code = e.response.status_code
            if code >= 500:
                msg = f"STATUS_CODE={code} {str(e)}"
            elif re.fullmatch(r'application/(hal\+)?json', e.response.headers['Content-Type']):
                res = {"ERROR": e.response.json()}
            else:
                err = e.response.content
                msg = str(err)
                log.error(f"{head_log} {msg}")
                res = {"ERROR": f"{head_log} {msg}"}
        except ConnectionResetError as e:
            res = {"ERROR": f"[CONNECTION] {head_log} ConnectionResetError {str(e)}"}
        except Exception as e:
            # log.error(txt := f"STATUS_CODE={e.response.status_code} {str(e)}")
            res = {"ERROR": f"[CONNECTION] {head_log} {str(e)}"}
        else:
            res = response.json() if response.text else {}
        return res

    def login(self) -> bool:
        """
        Realiza el login ante la API de Mutual Ser, asignándole el atributo
        self.sess_id y self.sess_timeout a partir de la respuesta de la
        API de Mutual Ser.
        Es llamado en su mayoría desde el decorator @login_required
        La respuesta exitosa luce así:

        :return: True or False
        """
        payload = {
            "grant_type": 'password',
            "client_secret": '023a1b60-09ed-4439-a970-ee81a3898825',
            "client_id": 'right-validation',
            "username": MS_USER,
            "password": MS_PASS
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        log.info("[MUTUAL] ...Realizando login")
        resp = self.request_api(
            'POST',
            f"{MS_API_URL}/{self.LOGIN}",
            headers=headers,
            payload='&'.join([f'{k}={v}' for k, v in payload.items()]),
        )
        if resp.get('access_token'):
            return self._extracted_from_login(resp)
        log.warning(f"[MUTUAL] Login no realizado, respuesta de MUTUAL: {resp!r}")
        return False

    def _extracted_from_login(self, resp):
        self.sess_id = resp['access_token']
        self.sess_timeout = moment() + datetime.timedelta(seconds=resp['expires_in'] - 60)
        log.info(
            f"[MUTUAL] Login realizado {format(moment(), '%r')}, se vencerá a las {format(self.sess_timeout, '%r')}")
        with open(self.LOGIN_CACHE, 'wb') as f:
            pickle.dump([self.sess_id, self.sess_timeout], f)
        return True

    def set_header(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {self.sess_id}"
        }

    def _parse_response(self, response: dict, endpoint: str):
        parsed_response = {}
        match endpoint:
            case self.VALIDADOR_DERECHOS:
                user = {}
                for k, v in response['entry'][0]['resource'].items():
                    if k == 'name':
                        user['NOMBRE'] = v[0]['text']
                        user['PRIMER_NOMBRE'] = v[0]['given'][0]
                        pairs = v[0]['family'].split('|')
                        apellidos = [pair.split('=')[1] for pair in pairs]
                        user['PRIMER_APELLIDO'] = apellidos[0]
                    elif k == 'extension':
                        for extension in v:  # extension tiene una lista de dicts
                            if 'afilliateStatus' in extension['url']:
                                user['status'] = extension['valueCoding']['display']
                    else:
                        continue
                parsed_response = user
            case _:
                ...
        return parsed_response

    @login_required
    def get_info_afiliado(self, tipo_documento: str, valor_documento: str):
        url = f'{MS_API_URL_VALIDADOR}/{self.VALIDADOR_DERECHOS}'
        body = {
            "resourceType": "Parameters",
            "id": "CorrelationId",
            "parameter": [
                {
                    "name": "documentType",
                    "valueString": f"{tipo_documento}"
                },
                {
                    "name": "documentId",
                    "valueString": f"{valor_documento}"
                }
            ]
        }
        resp = self.request_api(
            'POST', url,
            headers=self.set_header(),
            payload=json.dumps(body)
        )
        if 'ERROR' in resp and 'issue' in resp['ERROR']['entry'][0]['resource']:
            log.warning(f"[MUTUAL] Afiliado no encontrado, respuesta de API:"
                        f" {resp['ERROR']['entry'][0]['resource']['issue'][0]['details']['text']!r}")
            return {'NOMBRE': 'no existe',
                    'RESP API': resp['ERROR']['entry'][0]['resource']['issue'][0]['details']['text']}
        return self._parse_response(resp, self.VALIDADOR_DERECHOS)


if __name__ == '__main__':
    ms = MutualSerAPI()
    print(ms.get_info_afiliado('CC', '123456'))
