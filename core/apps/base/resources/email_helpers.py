import contextlib
import smtplib
import DNS
import socket

from decouple import config, Csv
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import get_template

from core.apps.base.resources.tools import notify, convert_bytes
from core.settings import logger, BASE_DIR


def get_complement_subject(payload: dict) -> str:
    """
    A partir del payload verifica si se trata de una
    radicación o un centro (inventario).
    """
    num_aut = payload.get('autorizacion') or payload.get('serial') or payload.get('Centro')
    if num_aut:
        if len(num_aut) < 4:
            num_aut = f"- Centro # {num_aut}"
        else:
            num_aut = f"- Radicado # {num_aut}"
    else:
        num_aut = ''
    return num_aut


def make_subject_and_cco(info_email) -> tuple:
    """
    Create the subject and establish the CCO.
    :param info_email: Dictionary with information captured from the wizard
    :return: Tuple with two elements:
                0 -> subject (str)
                1 -> copia_oculta (list)
    """

    copia_oculta = config('EMAIL_BCC', cast=Csv(), default=())

    # Definiendo asunto
    if info_email.get('documento'):
        subject = f"{info_email['NOMBRE'].title()} - Este es el " \
                  f"soporte de la radicación de tu domicilio en Logifarma"
    else:
        subject = f"{info_email['NUMERO_AUTORIZACION']} - Este es el " \
                  f"número de radicación de tu domicilio en Logifarma"

    if info_email.get('documento') in ('CC99999999',) or info_email.get('NUMERO_AUTORIZACION') in (
            99_999_999, 99_999_998):
        subject = '[OMITIR] CORREO DE PRUEBA'
        with contextlib.suppress(Exception):
            copia_oculta.remove('radicacion.domicilios@logifarma.co')

    return subject, copia_oculta


def purge_email(email) -> str:
    email = email.replace('gamil', 'gmail')
    email = email.replace('gemail', 'gmail')
    email = email.replace('gemaul', 'gmail')
    email = email.replace('logimarga', 'logifarma')
    if email in ('notiene@gmail.com'):
        return ''
    return email


def make_destinatary(info_email) -> list:
    """
    Validate if the e-mail exists.
    If doesn\'t exists then clean the field on info_mail.
    :param info_email: Dictionary with information captured from the wizard
    :return: Empty list or list with validated e-mail.
    """
    destinatary = []
    # If the email key comes and his first item of the list has something, then:
    if 'email' in info_email and info_email['email'][0]:
        for e in info_email['email']:
            if purge_email(e) and email_exists(e):
                destinatary.append(e)
            else:
                logger.info(f'Email {e} no existe.')
                info_email['email'].remove(e)
    return destinatary


def email_exists(email):
    return validar_email(email)


def get_mx(hostname):
    try:
        servidor_mx = DNS.mxlookup(hostname)
    except ServerError as e:
        if e.rcode in [3, 2]:  # NXDOMAIN (Non-Existent Domain) or SERVFAIL
            servidor_mx = None
        else:
            raise
    return servidor_mx


def validar_email(email, debug=False):
    try:
        hostname = email[email.find('@') + 1:]
        mx_hosts = get_mx(hostname)
        if mx_hosts is None:
            # print(f'No se encuentra MX para el dominio {hostname}')
            return None
        for mx in mx_hosts:
            try:
                # print(f'Servidor {mx[1]}')
                # print(f'Cuenta {email}')
                servidor = smtplib.SMTP(timeout=10)
                servidor.connect(mx[1])
                servidor.set_debuglevel(debug)
                status, _ = servidor.helo()
                if status != 250:
                    servidor.quit()
                    continue
                servidor.mail('')
                status, _ = servidor.rcpt(email)
                if status == 250:
                    servidor.quit()
                    return True
                servidor.quit()
            except smtplib.SMTPServerDisconnected:  # Server not permits verify user
                if debug:
                    print(f'{mx[1]} disconected.')
            except smtplib.SMTPConnectError:
                if debug:
                    print(f'Unable to connect to {mx[1]}.')
        return False
    except (ServerError, socket.error) as e:
        print(f'ServerError or socket.error exception raised ({e}).')
        return None


ServerError = DNS.ServerError


class Email:
    def __init__(self, foto=None, template=BASE_DIR / "core/apps/base/templates/notifiers/correo_sin_autorizacion.html"):
        self.log_text = None
        self.foto = foto
        self.template = get_template(template)

    def prepare_mail(self, info: dict) -> EmailMessage:
        subject, copia_oculta = self.make_subject_and_cco(info)
        destinatary = self.make_destinatary(info)
        html_content = self.template.render(info)
        email = EmailMessage(
            subject, html_content, to=destinatary, bcc=copia_oculta,
            from_email=f"Domicilios Logifarma <{settings.EMAIL_HOST_USER}>"
        )
        email.content_subtype = "html"

        if self.foto:
            # email.attach(self.foto_fmedica.name, self.foto_fmedica.new_file.file.read(), self.foto_fmedica.content_type)
            email.attach_file(str(settings.MEDIA_ROOT / self.foto.name))

        return email

    def send_mail(self, info) -> bool:
        """Envía email donde la imagen puede estar adjunta.
        :param info: Información enviada en el cuerpo del correo.
        :return: True caso haber enviado el correo, False en caso contrario
        """
        try:
            email = self.prepare_mail(info)

            if self.foto and not email.attachments:
                logger.error(f"{self.log_text} Perdida la referencia de imagen adjunta.")

            r = email.send(fail_silently=False)

        except Exception as e:
            notify('error-email',
                   f"ERROR ENVIANDO EMAIL- Radicado #{info['NUMERO_RADICACION']} {info['documento']}",
                   f"JSON_DATA: {info}\n\nERROR: {e}")
            return False
            # TODO Revisar que hacer cuando haya error en envío de email
            # if rad := Radicacion.objects.filter(numero_radicado=info['documento']).first():
            # rad.delete()
            # logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} {rad}"
            #             "Eliminado radicado al no haberse enviado correo.")
        else:
            if r == 1:
                if self.foto:
                    logger.info(f"{self.log_text} Correo enviado a {', '.join(info['email'])} con imagen adjunta")
                else:
                    logger.info(
                        f"{self.log_text} correo enviado a {info['email']} sin imagem")
                return True
            else:
                # E-mail enviado pero r != 1
                notify('error-email', f"ERROR ENVIANDO EMAIL - Radicado #{info['documento']}",
                       f"JSON_DATA: {info}")
                return False
        # finally:
        #     if self.foto:
        #         del_file(self.foto.file.file.name)

    def make_subject_and_cco(self, info) -> tuple:
        """
        Create the subject and establish the CCO.
        :param info: Dictionary with information captured from the wizard.
                     The next keys are used: 'NOMBRE', 'documento', 'NUMERO_AUTORIZACION'
        :return: Tuple with two elements:
                    0 -> subject (str)
                    1 -> copia_oculta (list)
        """

        copia_oculta = config('EMAIL_BCC', cast=Csv(), default=())

        # Definiendo asunto
        if info.get('documento'):
            subject = (f"F{info['NUMERO_RADICACION']} - Este es el "
                       "número de radicación de tu domicilio en Logifarma")
        else:
            subject = (f"{info['NUMERO_AUTORIZACION']} - Este es el "
                       f"número de radicación de tu domicilio en Logifarma")

        if info.get('documento') in ('CC99999999',) or info.get('NUMERO_AUTORIZACION') in (
                99_999_999, 99_999_998):
            subject = '[OMITIR] CORREO DE PRUEBA'
            with contextlib.suppress(Exception):
                copia_oculta.remove('radicacion.domicilios@logifarma.co')

        return subject, copia_oculta

    def make_destinatary(self, info) -> list:
        """
        Validate if the e-mail exists.
        If doesn\'t exists then clean the field on info_mail.
        :param info: Dictionary with information captured from the wizard
                    The next keys are used: 'email'
        :return: Empty list or list with validated e-mail.
        """
        destinatary = []
        # If the email key comes and his first item of the list has something, then:
        if 'email' in info and info['email'][0]:
            for e in info['email']:
                if purge_email(e) and email_exists(e):
                    destinatary.append(e)
                else:
                    logger.info(f'Email {e} no existe.')
                    info['email'].remove(e)
        return destinatary

