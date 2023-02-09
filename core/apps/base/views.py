import contextlib
import threading

from decouple import config, Csv
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
from core.apps.base.resources.tools import convert_bytes, del_file, is_file_valid, notify, guardar_info_bd
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

htmly = get_template(BASE_DIR / "core/apps/base/templates/correo.html")


def show_fotoFormulaMedica(cleaned_data) -> bool:
    """
    Determines if the 'fotoFormulaMedica' step have to be showed.
    Evaluate the cleaned data of the 'autorizacionServicio' step
    and checks if there is an ARCHIVO key on it. If this key is
    found, then will skip the 'fotoFormulaMedica' step.
    :param cleaned_data:
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
        logger.info('Validando si radicado tiene URL con formula médica.')
        url = cleaned_data['num_autorizacion']['ARCHIVO']
        rad = cleaned_data['num_autorizacion']['NUMERO_AUTORIZACION']
    except Exception as e:
        logger.warning(f'ARCHIVO (key) NO detectado en respuesta de API en radicado # {rad}.')
        notify('error-archivo-url', f'Radicado {rad} sin archivo.',
               f"RESPUESTA DE API: {cleaned_data}\n\n")
        return True
    else:
        return is_file_valid(url, rad)
    finally:
        logger.info('Validación de URL finalizada.')


class ContactWizard(CustomSessionWizard):
    # template_name = 'start.html'
    form_list = FORMS
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    condition_dict = {'fotoFormulaMedica': show_fotoFormulaMedica}

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def done(self, form_list, **kwargs):
        form_data = self.process_from_data(form_list)
        self.request.session['temp_data'] = form_data
        ContactWizard.new_form_list.clear()
        return HttpResponseRedirect(reverse('base:done'))

    @logtime('CORE')
    def process_from_data(self, form_list) -> dict:
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
        form_data = [form.cleaned_data for form in form_list]

        try:
            if form_data[2].get('src'):
                self.foto_fmedica = form_data[2]['src']
        except Exception as e:
            logger.error(f"No se pudo acceder a form_data[2]. {form_data=}", e)

        keys = list(self.new_form_list.keys())
        # Construye las variables que serán enviadas al template
        info_email = {
            **form_data[1]['num_autorizacion'],
            **form_data[keys.index('eligeMunicipio')],  # Ciudad
            **form_data[keys.index('digitaDireccionBarrio')],  # Barrio y dirección
            **form_data[keys.index('digitaCelular')],  # Celular
            **form_data[keys.index('digitaCorreo')],  # e-mail
        }

        # Guardará en BD cuando DEBUG sean números reales
        if info_email['NUMERO_AUTORIZACION'] not in [99_999_999, 99_999_998]:
            guardar_info_bd(**info_email, ip=self.request.META.get('HTTP_X_FORWARDED_FOR',
                                                                   self.request.META.get('REMOTE_ADDR')))

        logger.info(f'Radicación finalizada. E-mail de confirmación '
                    f"será enviado a {form_data[keys.index('digitaCorreo')]}")

        # Envía e-mail
        x = threading.Thread(target=self.send_mail, args=(info_email,))
        x.start()

        return form_data[1]['num_autorizacion']

    @staticmethod
    @logtime('EMAIL')
    def prepare_email(info_email):
        copia_oculta = config('EMAIL_BCC', cast=Csv())

        subject = f"{info_email['NUMERO_AUTORIZACION']} - Este es el " \
                  f"número de radicación de tu domicilio en Logifarma"

        if info_email['NUMERO_AUTORIZACION'] in [99_999_999, 99_999_998]:
            subject = '[OMITIR] CORREO DE PRUEBA'
            with contextlib.suppress(Exception):
                copia_oculta.remove('radicacion.domicilios@logifarma.co')

        destinatary = (info_email['email'],)
        html_content = htmly.render(info_email)

        email = EmailMessage(
            subject, html_content,
            from_email=f"Domicilios Logifarma <{settings.EMAIL_HOST_USER}>",
            to=destinatary,
            bcc=copia_oculta
        )
        email.content_subtype = "html"
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
                    logger.info(f"Correo enviado a {info_email['email']} con imagen "
                                f"adjunta de {convert_bytes(self.foto_fmedica.file.size)}.")
                else:
                    logger.info(f"Correo enviado a {info_email['email']} sin imagem")
            else:
                notify('error-email', f"ERROR ENVIANDO EMAIL- Radicado #{info_email['NUMERO_AUTORIZACION']}",
                       f"JSON_DATA: {info_email}")
        finally:
            if self.foto_fmedica:
                del_file(self.foto_fmedica.file.file.name)


def finalizado(request):
    if ctx := request.session.get('temp_data', {}):
        logger.info(f"Acessando a vista /finalizado al haber terminado el wizard. "
                    f"Radicado #{ctx['NUMERO_AUTORIZACION']}.")
        return render(request, 'done.html', ctx)
    else:
        logger.info('Se ha intentado acceder a vista /finalizado directamente')
        return HttpResponseRedirect('/')
