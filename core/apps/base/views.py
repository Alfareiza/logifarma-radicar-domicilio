import threading
from functools import lru_cache

from decouple import config
from django.core.files.storage import FileSystemStorage
from django.core.mail import EmailMessage
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import get_template
from django.urls import reverse

from core import settings
from core.apps.base.forms import *
from core.apps.base.resources.api_calls import check_meds
from core.apps.base.resources.customwizard import CustomSessionWizard
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.email_helpers import make_subject_and_cco, make_destinatary
from core.apps.base.resources.tools import convert_bytes, is_file_valid, notify, guardar_info_bd
from core.settings import logger, BASE_DIR

FORMS = [
    ("home", Home),
    ("autorizado_o_no", AutorizadoONo),
    ("autorizacionServicio", AutorizacionServicio),
    ("fotoFormulaMedica", FotoFormulaMedica),
    ("eligeMunicipio", EligeMunicipio),
    ("digitaDireccionBarrio", DireccionBarrio),
    ("digitaCelular", DigitaCelular),
    ("digitaCorreo", DigitaCorreo)
]

MANDATORIES_STEPS = ("home", "autorizado_o_no", "autorizacionServicio", "eligeMunicipio",
                     "digitaDireccionBarrio", "digitaCelular", "digitaCorreo")

TEMPLATES = {
    "home": "home.html",
    "sinAutorizacion": "sin_autorizacion.html",
    "autorizado_o_no": "autorizado_o_no.html",
    "autorizacionServicio": "autorizacion.html",
    "fotoFormulaMedica": "foto.html",
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
        logger.warning(f'{rad} ARCHIVO (key) NO detectado en respuesta de API en radicado.')
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
        # logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} Entrando en done {form_list=}")

        if self.steps_completed(**kwargs):
            form_data = self.process_from_data(form_list, **kwargs)
            self.request.session['ctx'] = form_data
            return HttpResponseRedirect(reverse('base:done'))

        self.request.session['ctx'] = {}
        logger.warning(f"{self.request.COOKIES.get('sessionid')[:6]} redireccionando "
                       f"a err_multitabs por multipestañas.")
        return HttpResponseRedirect(reverse('base:err_multitabs'))

    def steps_completed(self, **kwargs) -> bool:
        """Valida si todos los pasos obligatorios llegan al \'done\'"""
        return not bool(set(MANDATORIES_STEPS).difference(kwargs['form_dict']))

    @logtime('CORE')
    def process_from_data(self, form_list, **kwargs):
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
            logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} "
                        f"self.foto_fmedica={self.foto_fmedica}")

        # Construye las variables que serán enviadas al template
        info_email = {
            **form_data['autorizacionServicio']['num_autorizacion'],
            **form_data['eligeMunicipio'],
            **form_data['digitaDireccionBarrio'],
            **form_data['digitaCelular'],
            'email': [*form_data['digitaCorreo']]
        }
        # Guardará en BD cuando DEBUG sean números reales
        ip = self.request.META.get('HTTP_X_FORWARDED_FOR', self.request.META.get('REMOTE_ADDR'))
        if info_email['NUMERO_AUTORIZACION'] not in [99_999_999, 99_999_998]:
            guardar_info_bd(**info_email, ip=ip)

        logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} {info_email['NUMERO_AUTORIZACION']}"
                    f" Radicación finalizada. E-mail de confirmación será enviado a {form_data['digitaCorreo']}")

        # Revisa medicamentos
        # Deprecado 4-Dic-2024
        # if not config("DEBUG", cast=bool):
        #     ask_med = threading.Thread(target=check_meds, args=(info_email,))
        #     ask_med.start()

        # Envía e-mail
        if not self.foto_fmedica:
            x = threading.Thread(target=self.send_mail, args=(info_email,))
            x.start()
        else:
            self.send_mail(info_email)

        return form_data['autorizacionServicio']['num_autorizacion']

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
            uploaded = settings.MEDIA_ROOT / self.foto_fmedica.name
            logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} {info_email['NUMERO_AUTORIZACION']} "
                        f"adjuntando imagen {str(uploaded)}")
            email.attach_file(str(uploaded))
            if email.attachments:
                logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} {info_email['NUMERO_AUTORIZACION']} "
                            f"Imagen adjuntada con éxito.")
            else:
                logger.error(f"{self.request.COOKIES.get('sessionid')[:6]} {info_email['NUMERO_AUTORIZACION']} "
                             f"No se adjuntó la imagen. email.attachments={email.attachments}")

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
            if self.foto_fmedica and not email.attachments:
                logger.error(f"{self.request.COOKIES.get('sessionid')[:6]} {info_email['NUMERO_AUTORIZACION']} "
                             f"Perdida la referencia de imagen adjunta.")
            r = email.send(fail_silently=False)
        except Exception as e:
            notify('error-email', f"ERROR ENVIANDO EMAIL- Radicado #{info_email['NUMERO_AUTORIZACION']}",
                   f"JSON_DATA: {info_email}\n\nERROR: {e}")
            if rad := Radicacion.objects.filter(numero_radicado=info_email['NUMERO_AUTORIZACION']).first():
                ...
                # rad.delete()
                # logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} {rad}"
                #             "Eliminado radicado al no haberse enviado correo.")
        else:
            if r == 1:
                if self.foto_fmedica:
                    logger.info(
                        f"{self.request.COOKIES.get('sessionid')[:6]} {info_email['NUMERO_AUTORIZACION']} "
                        f"Correo enviado a {info_email['email']} con imagen adjunta de {convert_bytes(self.foto_fmedica.size)}.")
                else:
                    logger.info(
                        f"{self.request.COOKIES.get('sessionid')[:6]} {info_email['NUMERO_AUTORIZACION']} "
                        f"correo enviado a {info_email['email']} sin imagem")
            else:
                notify('error-email', f"ERROR ENVIANDO EMAIL- Radicado #{info_email['NUMERO_AUTORIZACION']}",
                       f"JSON_DATA: {info_email}")
        # finally:
        #     if self.foto_fmedica:
        #         del_file(self.foto_fmedica.file.file.name)


def finalizado(request):
    """
    Vista exhibida cuando el wizard es finalizado.
    :param request:
    Caso venga del flujo con cédula:
        - {'AFILIADO': 'DA SILVA RODRIQUEZ MARCELO SOUZA', 'DOCUMENTO_ID': '99999999',
         'NOMBRE': 'MARCELO DA SILVA', 'NUMERO_AUTORIZACION': '1',
         'P_NOMBRE': 'MARCELO',
         'TIPO_IDENTIFICACION': 'CC', 'documento': 'CC99999999'}
    Caso venga del flujo con número de autorización:
        - {'TIPO_IDENTIFICACION': 'CC', 'DOCUMENTO_ID': '12340316',
            'AFILIADO': 'GUTIERREZ TEIXEIRA JACKSON WOH',
            'P_NOMBRE': 'JACKSON',
            'S_NOMBRE': 'WOH', 'P_APELLIDO': 'GUTIERREZ',
            'S_APELLIDO': 'TEIXEIRA', 'ESTADO_AFILIADO': 'ACTIVO',
            'SEDE_AFILIADO': 'BARRANCABERMEJA', 'REGIMEN': 'SUBSIDIADO',
            'DIRECCION': 'CL 123  45 678',
            'CORREO': 'jackson.gutierrez.teixeira123456789@gmail.com',
            'TELEFONO': '4019255', 'CELULAR': '4014652512',
            'ESTADO_AUTORIZACION': 'PROCESADA', 'FECHA_AUTORIZACION': '15/11/2022',
            'MEDICO_TRATANTE': 'FRANK LAMPARD', 'MIPRES': '0',
            'DIAGNOSTICO': 'D571-ANEMIA FALCIFORME SIN CRISIS',
            'ARCHIVO': 'https://archivos-alfonso.s3.sa-east-1.amazonaws.com/doc1.pdf',
            'DETALLE_AUTORIZACION': [{'CUMS': '20158642-1', '
            NOMBRE_PRODUCTO': 'RIVAROXABAN 20MG TABLETA RECUBIERTA', 'CANTIDAD': '30'},
            {'CUMS': '42034-1', 'NOMBRE_PRODUCTO': 'HIDROXIUREA 500MG CAPSULA', 'CANTIDAD': '60'}],
            'municipio': 'Barrancamerbeja, Santander', 'barrio': 'Any Neighbor, Florida',
            'direccion': '321654987654', 'celular': 9151234567, 'email': '23131@gmail.com',
             'NUMERO_AUTORIZACION': 99999998}
    :return:
    """
    request.session['rendered_done'] = False
    if ctx := request.session.get('ctx', {}):
        logger.info(f"Autorización # {ctx['NUMERO_AUTORIZACION']!r} "
                    f"acessando a vista /finalizado al haber terminado el wizard.")
        return render(request, 'done.html', ctx)
    else:
        logger.info("Se ha intentado acceder a vista /finalizado directamente")
        return HttpResponseRedirect('/')


def err_multitabs(request):
    """Vista llamada cuando se detecte error de multi pestañas"""
    if 'ctx' in request.session:
        del request.session['ctx']
        return render(request, 'errors/multitabs.html')
    else:
        logger.info("Se ha intentado acceder a vista /error directamente")
        # Se puede agregar un mensaje para que aparezca un modal al
        # ser redireccionado al home.
        return HttpResponseRedirect('/')
