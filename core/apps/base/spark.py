import contextlib
import threading
from collections import OrderedDict
from functools import lru_cache

from decouple import config, Csv
from django.core.exceptions import SuspiciousOperation
from django.core.files.storage import FileSystemStorage
from django.core.mail import EmailMessage
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import get_template
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect
from formtools.wizard.forms import ManagementForm
from formtools.wizard.views import SessionWizardView

from core import settings
from core.apps.base.forms import *
from core.apps.base.models import Barrio
# from core.apps.base.resources.customwizard import CustomSessionWizard
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.tools import convert_bytes, is_file_valid, notify
from core.apps.base.resources.tools import parse_agent
from core.settings import BASE_DIR
from core.settings import logger


class OpaWizard(SessionWizardView):
    auth_serv = {}
    foto_fmedica = None
    _form_valids = OrderedDict()
    rad_data = None

    @property
    def form_valids(self):
        return self._form_valids

    @form_valids.setter
    def form_valids(self, value):
        print("some_value changed to", value)
        self._form_valids = value

    csrf_protected_method = method_decorator(csrf_protect)

    @csrf_protected_method
    def get(self, request, *args, **kwargs):
        sessionid = self.request.COOKIES.get('sessionid')
        if not sessionid:
            sessionid = 'Unknown'
        logger.info(f"${sessionid[:7]} "
                    f"IP={self.request.META.get('HTTP_X_FORWARDED_FOR', self.request.META.get('REMOTE_ADDR'))} entró en vista={self.request.resolver_match.url_name}")
        return super().get(request, *args, **kwargs)

    @csrf_protected_method
    def post(self, *args, **kwargs):
        """
        This method handles POST requests.

        The wizard will render either the current step (if form validation
        wasn't successful), the next step (if the current step was stored
        successful) or the done view (if no more steps are available)
        """
        method = self.request.method
        logger.info(f"Formularios válidos -> {self._form_valids}")
        logger.info(
            f"${self.request.COOKIES.get('sessionid')[:6]} IP={self.request.META.get('HTTP_X_FORWARDED_FOR', self.request.META.get('REMOTE_ADDR'))} "
            f"agent={parse_agent(self.request.META.get('HTTP_USER_AGENT'))} "
            f"saliendo_de={self.steps.current}")
        # Look for a wizard_goto_step element in the posted data which
        # contains a valid step name. If one was found, render the requested
        # form. (This makes stepping back a lot easier).

        wizard_goto_step = self.request.POST.get('wizard_goto_step', None)
        if wizard_goto_step and wizard_goto_step in self.get_form_list():
            return self.render_goto_step(wizard_goto_step)

        # Check if form was refreshed
        management_form = ManagementForm(self.request.POST, prefix=self.prefix)
        if not management_form.is_valid():
            raise SuspiciousOperation(_('ManagementForm data is missing or has been tampered.'))

        form_current_step = management_form.cleaned_data['current_step']
        if (form_current_step != self.steps.current and
                self.storage.current_step is not None):
            # form refreshed, change current step
            self.storage.current_step = form_current_step

        # get the form for the current step
        form = self.get_form(data=self.request.POST, files=self.request.FILES)

        # and try to validate
        if form.is_valid():
            # if the form is valid, store the cleaned data and files.
            print(f'==> {form.prefix} is valid...')
            self._form_valids[form.prefix] = form
            if form.prefix == "autorizacionServicio":
                self.rad_data = form.cleaned_data
            self.storage.set_step_data(self.steps.current, self.process_step(form))
            self.storage.set_step_files(self.steps.current, self.process_step_files(form))

            # check if the current step is the last step
            if self.steps.current == self.steps.last:
                # no more steps, render done view
                return self.render_done(form, **kwargs)
            else:
                # proceed to the next step
                return self.render_next_step(form)
        return self.render(form)

    def process_step(self, form):
        """
        Se ejecuta al hacer el post del current step.
        Guarda en self.auth_serv el cleaned_data del formulario de autorizacionServicio
        :param form: Html del formulario actual.
            Ex.:<tr>
                    <th>
                        <label for="id_autorizacionServicio-num_autorizacion">
                        Num autorizacion:</label>
                    </th>
                    <td>
                        <input type="number" name="autorizacionServicio-num_autorizacion"
                        value="123456789" min="100000"
                        required id="id_autorizacionServicio-num_autorizacion">
                    </td>
                </tr>
        :return:
            Ex.:
                <QueryDict:
                    {
                    'csrfmiddlewaretoken': ['b0m1...Hc8LX'],
                    'contact_wizard-current_step': ['autorizacionServicio'],
                    'autorizacionServicio-num_autorizacion': ['123456789']
                    }
                >
        """
        idx_view = list(self.form_list).index(self.steps.current)
        if not form.cleaned_data:
            logger.info(f"${self.request.COOKIES.get('sessionid')[:7]} No fue capturado "
                        f"nada en vista{idx_view}={self.steps.current}")
        else:
            logger.info(
                f"${self.request.COOKIES.get('sessionid')[:7]} vista{idx_view}={self.steps.current}, capturado={form.cleaned_data}")
        ls_form_list = self.form_list.keys()
        logger.info(
            f"${self.request.COOKIES.get('sessionid')[:7]} Al salir de {self.steps.current} las vistas son {list(ls_form_list)}")
        logger.info(f"${self.request.COOKIES.get('sessionid')[:7]} Formularios validos : {self._form_valids}")

        return self.get_form_step_data(form)

    def render_goto_step(self, *args, **kwargs):
        """
        Es ejecutado cuando se clica en el botón "Atrás", y en caso de clicar
        en el botón "Atrás" en la vista de foto, va a resetear la variable
        new_form_list.
        :param args:
        :param kwargs:
        :return:
        """
        logger.info(f"${self.request.COOKIES.get('sessionid')[:6]} Acabó de clicar "
                    f"en \'< Atrás\' para ir de {self.steps.current} a {args[0]}.")
        form = self.get_form(data=self.request.POST, files=self.request.FILES)
        # self.storage.set_step_data(self.steps.current, self.process_step(form))
        self.storage.set_step_files(self.steps.first, self.process_step_files(form))
        return super().render_goto_step(*args, **kwargs)

    def get_form(self, step=None, data=None, files=None):
        """
        Renderiza el formulario con el fin de preestablecer campos
        al iniciar la vista
        :param step: None
        :param data: None
        :param files: None
        :return: Formulario de vista 7 con información de barrio diligenciada
                 a partir de municipio escogido en vista 6
        """
        form = super(OpaWizard, self).get_form(step, data, files)
        step = step or self.steps.current
        if step == 'digitaDireccionBarrio':
            if form1_cleaned_data := self.get_cleaned_data_for_step('eligeMunicipio'):
                barrios_mun = Barrio.objects.filter(
                    municipio__id=form1_cleaned_data['municipio'].id
                ).order_by('name')
                form.fields['barrio'].choices = [(str(b.id), b.name.title()) for b in barrios_mun]
        return form

    def render_done(self, form, **kwargs):
        """
        This method gets called when all forms passed. The method should also
        re-validate all steps to prevent manipulation. If any form fails to
        validate, `render_revalidation_failure` should get called.
        If everything is fine call `done`.
        """

        final_forms = OrderedDict()
        # walk through the form list and try to validate the data again.
        for form_key, form_obj in self._form_valids.items():
            final_forms[form_key] = form_obj
        return self.done(list(final_forms.values()), form_dict=final_forms, **kwargs)



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
        logger.info(f"${ssid[:7]} Validando si radicado tiene URL con formula médica.")
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
        logger.info(f"${ssid[:7]} Validación de URL finalizada.")


class Spark(OpaWizard):
    # template_name = 'start.html'
    form_list = FORMS
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    condition_dict = {'fotoFormulaMedica': show_fotoFormulaMedica}

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def done(self, form_list, **kwargs):
        logger.info(f"${self.request.COOKIES.get('sessionid')[:6]} Entrando en done {form_list=}")
        form_data = self.process_from_data(form_list)
        self.request.session['temp_data'] = form_data
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
        # form_data = [form.cleaned_data for form in form_list]
        form_data = {form.prefix: form.cleaned_data for form in form_list}

        if 'fotoFormulaMedica' in form_data:
            self.foto_fmedica = form_data['fotoFormulaMedica']['src']

        # Construye las variables que serán enviadas al template
        info_email = {
            **form_data['autorizacionServicio']['num_autorizacion'],
            **form_data['eligeMunicipio'],  # Ciudad
            **form_data['digitaDireccionBarrio'],  # Barrio y dirección
            **form_data['digitaCelular'],  # Celular
            **form_data['digitaCorreo'],  # e-mail
        }

        # Guardará en BD cuando DEBUG sean números reales
        # if info_email['NUMERO_AUTORIZACION'] not in [99_999_999, 99_999_998]:
        #     guardar_info_bd(**info_email, ip=self.request.META.get('HTTP_X_FORWARDED_FOR',
        #                                                            self.request.META.get('REMOTE_ADDR')))

        logger.info(f"${self.request.COOKIES.get('sessionid')[:6]} Radicación finalizada. E-mail de confirmación "
                    f"será enviado a {form_data['digitaCorreo']}")

        # Envía e-mail
        x = threading.Thread(target=self.send_mail, args=(info_email,))
        x.start()

        return form_data['autorizacionServicio']['num_autorizacion']

    @logtime('EMAIL')
    def prepare_email(self, info_email):
        copia_oculta = config('EMAIL_BCC', cast=Csv())

        # subject = f"{info_email['NUMERO_AUTORIZACION']} - Este es el " \
        #           f"número de radicación de tu domicilio en Logifarma"

        # if info_email['NUMERO_AUTORIZACION'] in [99_999_999, 99_999_998]:
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
                        f"${self.request.COOKIES.get('sessionid')[:7]} Correo enviado a {info_email['email']} con imagen "
                        f"adjunta de {convert_bytes(self.foto_fmedica.size)}.")
                else:
                    logger.info(
                        f"${self.request.COOKIES.get('sessionid')[:7]} Correo enviado a {info_email['email']} sin imagem")
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
