from django.core.files.storage import FileSystemStorage
from django.core.mail import EmailMessage
from django.http import HttpResponseRedirect
from django.template.loader import get_template
from django.urls import reverse

from core import settings
from core.apps.base.forms import *
from core.apps.base.resources.customwizard import CustomSessionWizard
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.email_helpers import make_subject_and_cco, make_destinatary
from core.apps.base.resources.tools import convert_bytes, notify, guardar_short_info_bd
from core.settings import logger, BASE_DIR

FORMS = [
    ("sinAutorizacion", SinAutorizacion),
    ("fotoFormulaMedica", FotoFormulaMedica),
    ("eligeMunicipio", EligeMunicipio),
    ("digitaDireccionBarrio", DireccionBarrio),
    ("digitaCelular", DigitaCelular),
    ("digitaCorreo", DigitaCorreo)
]

MANDATORIES_STEPS = ("sinAutorizacion", "eligeMunicipio",
                     "digitaDireccionBarrio", "digitaCelular", "digitaCorreo")

TEMPLATES = {
    "sinAutorizacion": "sin_autorizacion.html",
    "fotoFormulaMedica": "foto.html",
    "eligeMunicipio": "elige_municipio.html",
    "digitaDireccionBarrio": "direccion_barrio.html",
    "digitaCelular": "digita_celular.html",
    "digitaCorreo": "digita_correo.html"}

htmly = get_template(BASE_DIR / "core/apps/base/templates/notifiers/correo_sin_autorizacion.html")


class SinAutorizacion(CustomSessionWizard):
    # template_name = 'start.html'
    form_list = FORMS
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)

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
        en el paso sinAutorizacion.
        A partir de algunos datos de la API de la EPS.
            - form_data[1] posee la información de la API de la EPS
            - form_data[2] (opcional) posee la información de la imagen.
        :param form_list: List de diccionarios donde cada index es el
                          resultado de lo capturado en cada formulario.
                          Cada key es el declarado en cada form.
        :return: Información capturada en el paso sinAutorizacion.
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
            **form_data['sinAutorizacion'],
            **form_data['eligeMunicipio'],
            **form_data['digitaDireccionBarrio'],
            **form_data['digitaCelular'],
            'email': [*form_data['digitaCorreo']]
        }

        # Guardará en BD cuando DEBUG sean números reales
        ip = self.request.META.get('HTTP_X_FORWARDED_FOR', self.request.META.get('REMOTE_ADDR'))
        if info_email['documento'][2:] not in ('99999999', ):
            rad = guardar_short_info_bd(**info_email, ip=ip)
            rad_id = rad.numero_radicado
            info_email['NUMERO_RADICACION'] = rad_id
            info_email['FECHA_RADICACION'] = rad.datetime
        else:
            rad_id = '1'

        # rad_id = guardar_short_info_bd(**info_email, ip=ip)

        # Envía e-mail
        if rad_id:
            self.log_text = f"{self.request.COOKIES.get('sessionid')[:6]} {rad_id=} {info_email['documento']}"

            logger.info(f"{self.log_text} {info_email['NOMBRE']} Radicación finalizada. "
                        f"E-mail de confirmación será enviado a {form_data['digitaCorreo']}")

            self.send_mail(info_email)

        # Se usa NUMERO_AUTORIZACION porque es el valor que /finalizado espera
        return {'NUMERO_AUTORIZACION': info_email['NOMBRE']}


    def prepare_email(self, info_email) -> EmailMessage:
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
            logger.info(f"{self.log_text} adjuntando imagen {str(uploaded)}")
            email.attach_file(str(uploaded))
            if email.attachments:
                logger.info(f"{self.log_text} Imagen adjuntada con éxito.")
            else:
                logger.error(f"{self.log_text} No se adjuntó la imagen. "
                             f"email.attachments={email.attachments}")

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
                logger.error(f"{self.log_text} Perdida la referencia de imagen adjunta.")
            r = email.send(fail_silently=False)
        except Exception as e:
            notify('error-email', f"ERROR ENVIANDO EMAIL- Radicado #{info_email['rad_id']} {info_email['documento']}",
                   f"JSON_DATA: {info_email}\n\nERROR: {e}")
            if rad := Radicacion.objects.filter(numero_radicado=info_email['documento']).first():
                ...
                # rad.delete()
                # logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} {rad}"
                #             "Eliminado radicado al no haberse enviado correo.")
        else:
            if r == 1:
                if self.foto_fmedica:
                    logger.info(
                        f"{self.log_text} Correo enviado a {info_email['email']} con imagen"
                        f" adjunta de {convert_bytes(self.foto_fmedica.size)}.")
                else:
                    logger.info(
                        f"{self.log_text} correo enviado a {info_email['email']} sin imagem")
            else:
                notify('error-email', f"ERROR ENVIANDO EMAIL- Radicado #{info_email['documento']}",
                       f"JSON_DATA: {info_email}")
        # finally:
        #     if self.foto_fmedica:
        #         del_file(self.foto_fmedica.file.file.name)
