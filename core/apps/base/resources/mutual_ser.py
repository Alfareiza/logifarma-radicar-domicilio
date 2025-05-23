import datetime
import json
import logging
import pickle
import re

import requests
from decorator import contextmanager
from requests import Timeout, HTTPError
from retry import retry

from core.apps.base.exceptions import UserNotFound, NroAutorizacionNoEncontrado, FieldError

from core.apps.base.resources.decorators import login_required
from core.apps.base.resources.selenium_manager import MutualSerSite
from core.apps.base.resources.tools import moment, add_user_id_to_formatter
from core.apps.tasks.utils.dt_utils import Timer
from core.settings import BASE_DIR, MS_PASS, MS_USER, MS_API_URL, MS_API_URL_VALIDADOR, ZONA_SER_URL
from core.settings import ch, logger as log


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
        # log.info("[MUTUAL] ...Realizando login")
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
        # log.info(
        #     f"[MUTUAL] Login realizado {format(moment(), '%r')}, se vencerá a las {format(self.sess_timeout, '%r')}")
        with open(self.LOGIN_CACHE, 'wb') as f:
            pickle.dump([self.sess_id, self.sess_timeout], f)
        return True

    def set_header(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {self.sess_id}"
        }

    def _parse_error_response(self, resp) -> dict:
        """Trata la respuesta de la API cuando se detectó un error."""
        if not isinstance(resp['ERROR'], dict):  # Cuando la respuesta de la API es un html
            return {}
        try:
            # Al colocarse en un try me aseguro que el camino para llegar al texto del error puede estar errado
            if 'issue' in resp['ERROR']['entry'][0]['resource']:
                log.warning(f"[MUTUAL] Afiliado no encontrado, respuesta de API:"
                            f" {resp['ERROR']['entry'][0]['resource']['issue'][0]['details']['text']!r}")
                return {'NOMBRE': 'no existe',
                        'RESP API': resp['ERROR']['entry'][0]['resource']['issue'][0]['details']['text']}
        except (TypeError, KeyError):
            return {}

    def _parse_response(self, response: dict, endpoint: str):
        if 'ERROR' in response:
            return self._parse_error_response(response)
        parsed_response = {}
        match endpoint:
            case self.VALIDADOR_DERECHOS:
                try:
                    user = self._extract_info_afiliado_from_api_response(response)
                except (TypeError, KeyError) as e:
                    log.warning(f"API respondió exitosamente pero no se puedo parsear su respuesta: {str(e)}")
                    return {}
                parsed_response = user
            case _:
                ...
        return parsed_response

    @staticmethod
    def _extract_info_afiliado_from_api_response(response):
        """Dada la respuesta de la API, extrae el nombre completo, primer nombre, primer appelido y estatus del
        afiliado."""
        user = {}
        for k, v in response['entry'][0]['resource'].items():
            if k == 'extension':
                for extension in v:  # extension tiene una lista de dicts
                    if 'afilliateStatus' in extension['url']:
                        user['status'] = extension['valueCoding']['display']
            elif k == 'name':
                user['NOMBRE'] = v[0]['text']
                user['PRIMER_NOMBRE'] = v[0]['given'][0]
                pairs = v[0]['family'].split('|')
                apellidos = [pair.split('=')[1] for pair in pairs]
                user['PRIMER_APELLIDO'] = apellidos[0]
            else:
                continue
        return user

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
        return self._parse_response(resp, self.VALIDADOR_DERECHOS)


class MutualSerPage:
    IDENTIFICACIONES = {
        'CC': 'Cedula de Ciudadania',
        'CE': 'Cedula de Extranjeria',
        'TI': 'Tarjeta de Identidad',
        'RC': 'Registro Civil',
        'PA': 'Pasaporte',
        'MS': 'Menor sin Identificacion',
        'PE': 'Permiso Especial',
        'CN': 'Certificado Nacido Vivo',
        'PT': 'Permiso Temporal',
        'SC': 'Salvo Conducto',
    }

    def __init__(self, url: str):
        self.url = url
        self.page = MutualSerSite()

    @contextmanager
    def open_page(self, acr_tipo_documento, documento):
        self.page.open_browser()
        # self.browser.set_window_size(1920, 1080)
        handler = log.handlers[0]  # Keep a reference
        original_formatter = handler.formatter
        add_user_id_to_formatter(handler, f"{acr_tipo_documento}{documento}")
        yield
        ch.setFormatter(original_formatter)
        self.browser.close_all_browsers()

    @property
    def browser(self):
        return self.page.browser

    def login(self):
        self.page.login.perform(self.url, self.browser)

    def search_user(self, tipo_documento, documento) -> dict:
        """Busca usuario en portal de Mutual Ser."""
        log.info('Diligenciando formulario para buscar usuario')
        try:
            patient_data = self.page.search_page.perform(self.browser, tipo_documento, documento)
        except UserNotFound as e:
            log.warning(str(e))
            return {'MSG': 'Usuario no encontrado en Mutual Ser.'}
        except NroAutorizacionNoEncontrado as e:
            log.warning(str(e))
            return {'MSG': 'Numero de autorización no encontrado para usuario.'}
        except FieldError as e:
            log.warning(str(e))
            return {'MSG': str(e)}
        except Exception as e:
            log.warning(str(e))
            raise
        else:
            return patient_data
        finally:
            log.info('Búsqueda finalizada')

    @retry(TimeoutError, 2, delay=2)
    def find_user(self, acr_tipo_documento, documento):
        """Busca un usuario en página de mutual ser y si durante cada recorrido se
        demora más de 45 segundos, aborta y vuelve a empezar.
        """
        timer = Timer(45)
        while timer.not_expired:
            if not (tipo_documento := self.IDENTIFICACIONES.get(acr_tipo_documento)):
                return {'MSG': f'Tipo de documento {tipo_documento!r} no reconocido.'}
            with self.open_page(acr_tipo_documento, documento):
                self.login()
                return self.search_user(tipo_documento, documento)

        raise TimeoutError("Se intentó dos veces buscar el usuario pero en c/u se demoró más de 45 segundos.")


if __name__ == '__main__':
    # ms = MutualSerAPI()
    # print(ms.get_info_afiliado('CC', '123456'))

    site = MutualSerPage(ZONA_SER_URL)
    result = site.find_user('PT', '123123123')
    from pprint import pprint

    pprint(result)
