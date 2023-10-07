import contextlib
import smtplib
import DNS
import socket

from decouple import config, Csv

from core.settings import logger


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
    copia_oculta = config('EMAIL_BCC', cast=Csv())

    subject = f"{info_email['NUMERO_AUTORIZACION']} - Este es el " \
              f"número de radicación de tu domicilio en Logifarma"

    if info_email['NUMERO_AUTORIZACION'] in [99_999_999, 99_999_998]:
        subject = '[OMITIR] CORREO DE PRUEBA'
        with contextlib.suppress(Exception):
            copia_oculta.remove('radicacion.domicilios@logifarma.co')

    return subject, copia_oculta


def purge_email(email) -> str:
    email = email.replace('gamil', 'gmail')
    email = email.replace('gemail', 'gmail')
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
