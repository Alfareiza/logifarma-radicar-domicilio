import threading
import traceback
from functools import lru_cache
from io import BytesIO

from django.core.files.storage import FileSystemStorage
from django.core.mail import EmailMessage
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.template.loader import get_template
from retry import retry
from xhtml2pdf import pisa

from core import settings
from core.apps.base.forms import *
from core.apps.base.resources.customwizard import CustomSessionWizard
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.email_helpers import make_subject_and_cco, make_destinatary
from core.apps.base.resources.sms_helpers import send_sms_confirmation
from core.apps.base.resources.tools import convert_bytes, is_file_valid, notify, guardar_info_bd, clean_ip
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

TEMPLATES = {
    "home": "home.html",
    "home_prueba": "home_prueba.html",
    # Usado en /sin-autorizacion usuarios mutualser/fomag/cajacopi
    "sinAutorizacion": "sin_autorizacion.html",
    # Usuario escoge si su medicamento es autorizado o no
    "autorizado_o_no": "autorizado_o_no.html",
    # Usado en / usuarios cajacopi con medicamento autorizado
    "autorizacionServicio": "autorizacion.html",
    # Usado en /mutualser, exhibe un resumen de sus autorizaciones
    "autorizacionesPorDisp": "autorizacion_por_disp.html",
    "orden": "orden.html",
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
    """Clase responsable por el wizard para Cajacopi - Medicamentos autorizados."""
    # template_name = 'start.html'
    form_list = FORMS
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    condition_dict = {'fotoFormulaMedica': show_fotoFormulaMedica}
    MANDATORIES_STEPS = ("home", "autorizado_o_no", "autorizacionServicio", "eligeMunicipio",
                         "digitaDireccionBarrio", "digitaCelular", "digitaCorreo")

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def get_form_kwargs(self, step, *args, **kwargs):
        """Pass wizard instance to forms that need access to previous step data"""
        kwargs = super().get_form_kwargs(step, *args, **kwargs)
        if step == 'digitaCelular':
            kwargs['wizard'] = self
        return kwargs

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
        info = self.prepare_info_to_store_rad(info_email)
        if info['NUMERO_AUTORIZACION'] not in [99_999_999, 99_999_998]:
            guardar_info_bd(**info)
        # else:
        #     Radicacion(cel_uno=info['celular'], numero_radicado=info['NUMERO_AUTORIZACION'])

        logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} {info_email['NUMERO_AUTORIZACION']}"
                    f" Radicación finalizada. E-mail de confirmación será enviado a {form_data['digitaCorreo']}")

        # Revisa medicamentos
        # Deprecado 4-Dic-2024
        # if not config("DEBUG", cast=bool):
        #     ask_med = threading.Thread(target=check_meds, args=(info_email,))
        #     ask_med.start()

        # Envía e-mail
        if not self.foto_fmedica:
            x = threading.Thread(target=self.send_mail, args=(info,))
            x.start()
        else:
            self.send_mail(info)
            send_sms_confirmation(info['celular'], info['NUMERO_AUTORIZACION'], info['P_NOMBRE'])

        return self.prepare_info_to_done_step(info)

    def prepare_email(self, info_email):

        @retry(tries=3, delay=5)
        def attach_file(email: 'EmailMessage', file_path: str):
            email.attach_file(file_path)

        subject, copia_oculta = make_subject_and_cco(info_email)
        destinatary = make_destinatary(info_email)
        info_email.update(
            {
                'LOGO': "https://domicilios.logifarma.com.co/static/img/cajacopi_logo.png",
                'WIDTH': '36%',
            }
        )
        html_content = htmly.render(info_email)
        email = EmailMessage(
            subject, html_content, to=destinatary, bcc=copia_oculta,
            from_email=f"Domicilios Logifarma <{settings.EMAIL_HOST_USER}>"
        )
        email.content_subtype = "html"

        if self.foto_fmedica:
            uploaded = settings.MEDIA_ROOT / self.foto_fmedica.name
            if uploaded.exists():
                str_exists_or_not = f'imagen {str(uploaded)!r} ya no existe :('
            else:
                str_exists_or_not = f'adjuntando imagen {str(uploaded)}'
            logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} {info_email['NUMERO_AUTORIZACION']} "
                        f"{str_exists_or_not} - {self.foto_fmedica}")

            attach_file(email, str(uploaded))
            if email.attachments:
                logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} {info_email['NUMERO_AUTORIZACION']} "
                            f"Imagen adjuntada con éxito.")
            else:
                logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} {info_email['NUMERO_AUTORIZACION']} "
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
        except FileNotFoundError as e:
            tracebk = '\n'.join(traceback.format_exc().splitlines())
            notify('error-archivo', f"ERROR CON ARCHIVO ENVIANDO EMAIL- Radicado #{info_email['NUMERO_AUTORIZACION']}",
                   f"JSON_DATA: {info_email}\n\nSession ID:{self.request.COOKIES.get('sessionid')[:6]}"
                   f"\n\nTraceback: \n{tracebk}")
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
                        f"Correo enviado a {info_email['email'] or ''} con imagen adjunta de {convert_bytes(self.foto_fmedica.size)}.")
                else:
                    logger.info(
                        f"{self.request.COOKIES.get('sessionid')[:6]} {info_email['NUMERO_AUTORIZACION']} "
                        f"correo enviado a {info_email['email'] or ''} sin imagen")
            else:
                notify('error-email', f"ERROR ENVIANDO EMAIL- Radicado #{info_email['NUMERO_AUTORIZACION']}",
                       f"JSON_DATA: {info_email}")
        # finally:
        #     if self.foto_fmedica:
        #         del_file(self.foto_fmedica.file.file.name)


    def prepare_info_to_store_rad(self, info):
        """ Crea un diccionario que será usado para guardar el radicado y tomado para construir el correo html. """
        return {
            'celular': info['celular'],
            'whatsapp': info.get('whatsapp'),
            'barrio': info.get('barrio'),
            'direccion': info.get('direccion'),
            'celular_validado': info.get('celular_validado'),
            'email': info.get('email', ['']),
            'municipio': info.get('municipio'),
            'IP': clean_ip(self.request.META.get('HTTP_X_FORWARDED_FOR', self.request.META.get('REMOTE_ADDR'))),
            'P_NOMBRE': info.get('P_NOMBRE', ''),  # 'JOSE'
            'NOMBRE': info.get('NOMBRE'),  # 'JOSE'
            'AFILIADO': info.get('AFILIADO'),  # 'JOSE JULIAN VIVES NULE'
            'DOCUMENTO_ID': info['DOCUMENTO_ID'],  # '12345678'
            'TIPO_IDENTIFICACION': info['TIPO_IDENTIFICACION'],  # 'CC'
            'CONVENIO': info.get('CONVENIO'),
            'NUMERO_AUTORIZACION': str(info['NUMERO_AUTORIZACION']),
            'MEDICAMENTO_AUTORIZADO': True,
            'PACIENTE_DATA': {
                'DETALLE_AUTORIZACION': info.get('DETALLE_AUTORIZACION'),
                "P_NOMBRE": info.get('P_NOMBRE'),
                "S_NOMBRE": info.get('S_NOMBRE'),
                "P_APELLIDO": info.get('P_APELLIDO'),
                "S_APELLIDO": info.get('S_APELLIDO'),
                "ARCHIVO": info.get('ARCHIVO', ""),
                "MIPRES": info.get('MIPRES'),
                "REGIMEN": info.get('REGIMEN'),
                "DIAGNOSTICO": info.get('DIAGNOSTICO'),
                "Observacion": info.get('Observacion'),
                "IPS_SOLICITA": info.get('IPS_SOLICITA'),
                "SEDE_AFILIADO": info.get('SEDE_AFILIADO'),
                "CORREO_RESP_AUT": info.get('CORREO_RESP_AUT'),
                "MEDICO_TRATANTE": info.get('MEDICO_TRATANTE'),
                "RESPONSABLE_AUT": info.get('RESPONSABLE_AUT'),
                "CORREO_RESP_GUARDA": info.get('CORREO_RESP_GUARDA'),
                "FECHA_AUTORIZACION": info.get('FECHA_AUTORIZACION'),
                "RESPONSABLE_GUARDA": info.get('RESPONSABLE_GUARDA'),
            }
        }

    @staticmethod
    def prepare_info_to_done_step(info: dict) -> dict:
        """Prepare info last step (done.html)."""
        return {
            'P_NOMBRE': info.get('P_NOMBRE'),  # 'JOSE'
            'AFILIADO': info.get('AFILIADO'),  # 'JOSE JULIAN VIVES NULE'
            'DOCUMENTO_ID': info['DOCUMENTO_ID'],  # '1234567'
            'TIPO_IDENTIFICACION': info['TIPO_IDENTIFICACION'],  # 'CC'
            'BARRIO': info.get('barrio'),
            'DIRECCION': info.get('direccion'),
            'CELULAR': info.get('celular'),
            'MUNICIPIO': str(info.get('municipio')),
            'CORREO': info['email'][0] if info['email'] else "",
            'AUTORIZACIONES': {info['NUMERO_AUTORIZACION']: info['PACIENTE_DATA']['DETALLE_AUTORIZACION']},
            'LEN_AUTORIZACIONES': len(info['PACIENTE_DATA']['DETALLE_AUTORIZACION']),
        }


def finalizado(request):
    """Vista exhibida cuando el wizard es finalizado.
    Para saber que información viene aqui es necesario observar las funciones pepare_info_to_done_step',
    """
    request.session['rendered_done'] = False
    if ctx := request.session.get('ctx', {}):
        autorizaciones = ctx.get('NUMERO_AUTORIZACION') or ', '.join(list(ctx.get('AUTORIZACIONES', {}).keys()))
        logger.info(f"{autorizaciones} <- Autorización, "
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
