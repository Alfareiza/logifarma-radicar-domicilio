import threading
from functools import lru_cache

from django.core.files.storage import FileSystemStorage
from django.core.mail import EmailMessage
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import get_template
from django.urls import reverse

from core import settings
from core.apps.base.forms import *
from core.apps.base.resources.customwizard import CustomSessionWizard
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.email_helpers import make_subject_and_cco, make_destinatary
from core.apps.base.resources.tools import convert_bytes, is_file_valid, notify, guardar_info_bd
from core.settings import logger, BASE_DIR

FORMS = [
    ("home", Home),
    # ("instrucciones", Instrucciones),
    ("autorizacionServicio", AutorizacionServicio),
    ("fotoFormulaMedica", FotoFormulaMedica),
    # ("avisoDireccion", AvisoDireccion),
    ("eligeMunicipio", EligeMunicipio),
    ("digitaDireccionBarrio", DireccionBarrio),
    ("digitaCelular", DigitaCelular),
    ("digitaCorreo", DigitaCorreo)
]

TEMPLATES = {
    "home": "home.html",
    # "instrucciones": "instrucciones.html",
    "autorizacionServicio": "autorizacion.html",
    "fotoFormulaMedica": "foto.html",
    # "avisoDireccion": "aviso_direccion.html",
    "eligeMunicipio": "elige_municipio.html",
    "digitaDireccionBarrio": "direccion_barrio.html",
    "digitaCelular": "digita_celular.html",
    "digitaCorreo": "digita_correo.html"}

htmly = get_template(BASE_DIR / "core/apps/base/templates/notifiers/correo.html")


@lru_cache
def show_fotoFormulaMedica(wizard) -> bool:
    """
    Determines if the 'fotoFormulaMedica' step have to be showed.
    Evaluate the cleaned data of the 'autorizacionServicio' step
    and checks if there is an ARCHIVO key on it. If this key is
    found, then will skip the 'fotoFormulaMedica' step.
    :param wizard.rad_data:
           {'num_autorizacion':
                    {
                      ...
                      'ARCHIVO': 'https://genesis.cajacopieps.com/temp/63dd11940fb6a.pdf',
                      ...
                    }
           }

    :return: True or False
    """
    try:
        ssid = wizard.request.COOKIES.get('sessionid')
        if not ssid:
            ssid = 'Unknown'
        # logger.info(f"{ssid[:7]} Validando si radicado tiene URL con formula médica.")
        if cleaned_data := wizard.rad_data:
            url = cleaned_data['num_autorizacion']['ARCHIVO']
            rad = cleaned_data['num_autorizacion']['NUMERO_AUTORIZACION']
            return is_file_valid(url, rad)
        return True
    except Exception as e:
        logger.warning(f'ARCHIVO (key) NO detectado en respuesta de API en radicado # {rad}.')
        notify('error-archivo-url', f'Radicado {rad} sin archivo.',
               f"RESPUESTA DE API: {cleaned_data}\n\n")
        return True
    finally:
        ...
        # logger.info(f"{ssid[:7]} Validación de URL finalizada.")


class ContactWizard(CustomSessionWizard):
    # template_name = 'start.html'
    form_list = FORMS
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    condition_dict = {'fotoFormulaMedica': show_fotoFormulaMedica}

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def done(self, form_list, **kwargs):
        logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} Entrando en done {form_list=}")
        form_data = self.process_from_data(form_list, **kwargs)
        self.request.session['temp_data'] = form_data
        return HttpResponseRedirect(reverse('base:done'))

    @logtime('CORE')
    def process_from_data(self, form_list, **kwargs) -> dict:
        """
        Guarda en base de datos y envía el correo con la información capturada
        en el paso autorizacionServicio.
        A partir de algunos datos de la API de la EPS.
            - form_data[1] posee la información de la API de la EPS
            - form_data[2] (opcional) posee la información de la imagen.
        :param form_list: List de diccionarios donde cada index es el
                          resultado de lo capturado en cada formulario.
                          Cada key es el declarado en cada form.
        :return: Información capturada en el paso autorizacionServicio.
                En caso de querer mostrar alguna información en el done.html
                se debe retonar en esta función.
        """
        # form_data = [form.cleaned_data for form in form_list]
        form_data = {k: v.cleaned_data for k, v in kwargs['form_dict'].items()}

        if 'fotoFormulaMedica' in form_data:
            self.foto_fmedica = form_data['fotoFormulaMedica']['src']

        # Construye las variables que serán enviadas al template
        info_email = {
            **form_data['autorizacionServicio']['num_autorizacion'],
            **form_data['eligeMunicipio'],
            **form_data['digitaDireccionBarrio'],
            **form_data['digitaCelular'],
            'email': [*form_data['digitaCorreo']]
            }

        # Guardará en BD cuando DEBUG sean números reales
        if info_email['NUMERO_AUTORIZACION'] not in [99_999_999, 99_999_998]:
            guardar_info_bd(**info_email, ip=self.request.META.get('HTTP_X_FORWARDED_FOR',
                                                                   self.request.META.get('REMOTE_ADDR')))

        logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} Radicación finalizada. E-mail de confirmación "
                    f"será enviado a {form_data['digitaCorreo']}")

        # Envía e-mail
        x = threading.Thread(target=self.send_mail, args=(info_email,))
        x.start()

        return form_data['autorizacionServicio']['num_autorizacion']

    @logtime('EMAIL')
    def prepare_email(self, info_email):
        subject, copia_oculta = make_subject_and_cco(info_email)
        destinatary = make_destinatary(info_email)
        html_content = htmly.render(info_email)
        email = EmailMessage(
            subject, html_content, to=destinatary, bcc=copia_oculta,
            from_email=f"Domicilios Logifarma <{settings.EMAIL_HOST_USER}>"
        )
        email.content_subtype = "html"

        if self.foto_fmedica:
            email.attach_file(settings.MEDIA_ROOT / self.foto_fmedica.name)

        return email

    @logtime('EMAIL')
    def send_mail(self, info_email):
        """
        Envía email donde la imagen puede estar adjunta.
        :param info_email: Información enviada en el cuerpo del correo.
        :return: None
        """
        try:
            email = self.prepare_email(info_email)
            r = email.send(fail_silently=False)
        except Exception as e:
            notify('error-email', f"ERROR ENVIANDO EMAIL- Radicado #{info_email['NUMERO_AUTORIZACION']}",
                   f"JSON_DATA: {info_email}\n\nERROR: {e}")
        else:
            if r == 1:
                if self.foto_fmedica:
                    logger.info(
                        f"{self.request.COOKIES.get('sessionid')[:6]} Correo enviado a {info_email['email']} con imagen "
                        f"adjunta de {convert_bytes(self.foto_fmedica.size)}.")
                else:
                    logger.info(
                        f"{self.request.COOKIES.get('sessionid')[:6]} Correo enviado a {info_email['email']} sin imagem")
            else:
                notify('error-email', f"ERROR ENVIANDO EMAIL- Radicado #{info_email['NUMERO_AUTORIZACION']}",
                       f"JSON_DATA: {info_email}")
        # finally:
        #     if self.foto_fmedica:
        #         del_file(self.foto_fmedica.file.file.name)


def finalizado(request):
    if ctx := request.session.get('temp_data', {}):
        logger.info(
            f"{request.COOKIES.get('sessionid')[:6]} Acessando a vista /finalizado al haber terminado el wizard. "
            f"Radicado #{ctx['NUMERO_AUTORIZACION']}.")
        return render(request, 'done.html', ctx)
    else:
        logger.info("Se ha intentado acceder a vista /finalizado directamente")
        return HttpResponseRedirect('/')
