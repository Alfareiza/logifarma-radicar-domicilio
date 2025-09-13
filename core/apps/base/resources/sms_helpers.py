from decouple import config

from core.apps.base.resources.movistar import ApiMovistar
from core.settings import PRODUCTION


class Sms(ApiMovistar):
    MOVISTAR_URL = config('MOVISTAR_URL')
    MESSAGE = 'sms/3/messages'

    def __init__(self, numero_celular):
        super().__init__()
        self.numero_celular = numero_celular

    def payload_sms(self, content):
        """Create body to be sent to the API base on destination number a content of message."""
        return {
            "messages": [
                {
                    "from": "LOGIFARMA",
                    "destinations": [
                        {
                            "to": f"57{self.numero_celular}"
                        }
                    ],
                    "content": {
                        "text": content
                    }
                }
            ]
        }

    def send_sms(self, message: str):
        """Send an sms message."""
        if not PRODUCTION:
            return True
        resp = self.post(f"{self.MOVISTAR_URL}{self.MESSAGE}", self.payload_sms(message))
        return not bool(resp.get('ERROR'))


def send_sms_verification_code(cel: int, otp_code: int):
    """Send a verification code."""
    return Sms(cel).send_sms(f"{otp_code}: código de verificación de Logifarma. No lo compartas.")

def send_sms_confirmation(cel: int, numero_autorizacion: str, p_nombre: str):
    """Send a verification code."""
    numero_autorizacion = numero_autorizacion.replace('#', '')
    hola = f"Hola {p_nombre.title()}".strip()
    return Sms(cel).send_sms(f"Logifarma: {hola}, Tu solicitud de entrega a domicilio Nº{numero_autorizacion} fue realizada con éxito!.")