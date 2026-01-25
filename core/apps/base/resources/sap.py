import json
import pickle
import datetime

import requests
from requests import Timeout, HTTPError

from core.apps.base.resources.decorators import login_required
from core.settings import SAP_COMPANY, SAP_USER, SAP_PASS, SAP_URL, BASE_DIR
from core.settings import logger as log
from core.apps.base.resources.tools import moment


class SAP:
    LOGIN_CACHE = BASE_DIR / 'login_sap.pickle'

    LOGIN = '/b1s/v2/Login'
    ENDPOINT_FOMAG = '/b1s/v2/sml.svc/InfoMagisterioQuery'

    def __init__(self):
        self.sess_id = ''
        self.sess_timeout = None

    # @logtime('API')
    def request_api(self, method, url, headers, payload=None) -> dict:
        if payload is None:
            payload = {}
        # sourcery skip: raise-specific-error
        res = {"ERROR": ""}
        timeout = 60
        head_log = '[SAP]'
        try:
            response = requests.request(method, url, headers=headers,
                                        data=json.dumps(payload),
                                        timeout=timeout)
            response.raise_for_status()
        except Timeout:
            log.error(txt := f"{head_log} No hubo respuesta de la API en {timeout} segundos")
            res = {"ERROR": f"[TIMEOUT] {txt}"}
        except HTTPError as e:
            code = e.response.status_code
            if code >= 500:
                msg = f"STATUS_CODE={code} {str(e)}"
            elif code == 400:
                msg = f"STATUS_CODE={code} {str(e)}"
            elif 'application/json' in e.response.headers['Content-Type']:
                msg = e.response.json()
            else:
                err = e.response.content
                if 'error' in err and err.get('error'):
                    msg = err['error']['message']
                else:
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
        Realiza el login ante la API de SAP, asignándole el atributo
        self.sess_id y self.sess_timeout a partir de la respuesta de la
        API de SAP.
        Es llamado en su mayoría desde el decorator @login_required
        La respuesta exitosa luce así:
            {
                '@odata.context': 'https://123456.heinsohncloud.com.
                co:50000/b1s/v2/$metadata#B1Sessions/$entity',
                'SessionId': '3643564asd-0181-11ee-8000-6045b3645e5bd5',
                'SessionTimeout': 30,
                'Version': '1000191'
            }
        :return: True or False
        """
        payload = {
            "CompanyDB": SAP_COMPANY,
            "UserName": SAP_USER,
            "Password": SAP_PASS,
            "Language": 25
        }
        headers = {'Content-Type': 'application/json'}
        # log.info("[SAP] ...Realizando login")
        resp = self.request_api(
            'POST',
            f"{SAP_URL}/{self.LOGIN}",
            headers=headers,
            payload=payload,
        )
        if resp.get('SessionId'):
            return self._extracted_from_login(resp)
        log.warning(f"[SAP] Login no realizado, respuesta de SAP: {resp!r}")
        return False

    def _extracted_from_login(self, resp):
        self.sess_id = resp['SessionId']
        self.sess_timeout = moment() + datetime.timedelta(minutes=resp['SessionTimeout'] - 1)
        # log.info(f"[SAP] Login realizado {format(moment(), '%r')}, se vencerá a las {format(self.sess_timeout, '%r')}")
        with open(self.LOGIN_CACHE, 'wb') as f:
            pickle.dump([self.sess_id, self.sess_timeout], f)
        return True

    def set_header(self):
        return {
            'Content-Type': 'application/json',
            'Cookie': f"B1SESSION={self.sess_id}"
        }

    def get(self, url):
        headers = self.set_header()
        return self.request_api('GET', url, headers=headers)

    @login_required
    def get_info_afiliado(self, tipo_documento, valor_documento):
        return self.get(f'{SAP_URL}{self.ENDPOINT_FOMAG}?$filter=Name eq \'{valor_documento}{tipo_documento}\'')
