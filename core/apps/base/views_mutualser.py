import random
from collections import OrderedDict

from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext as _
from django.http import HttpResponseRedirect, HttpResponse
from django.core.exceptions import SuspiciousOperation
from formtools.wizard.forms import ManagementForm

from core import settings
from core.apps.base.forms import *
from core.apps.base.legacy_models import Mutualser
from core.apps.base.models import ScrapMutualSer
from core.apps.base.pipelines import NotifyEmail, NotifySMS
from core.apps.base.resources.customwizard import CustomSessionWizard
from core.apps.base.validators import validate_resp_zona_ser, validate_dispensados
from core.apps.base.resources.decorators import logtime, once_in_interval
from core.apps.base.resources.tools import guardar_info_bd, notify
from core.apps.base.views import TEMPLATES
from core.settings import logger, BASE_DIR


class DocumentoMutualSer(forms.Form):
    """
    Vista 2 (Flujo sin autorización):
    Página que recibe núnero de cedula y
    verifica en API externas.
    Si la respuesta es positiva, se dirigirá a la
    vista FotoFormulaMedica, sino  responderá con un
    mensaje (modal) de error.
    """
    IDENTIFICACIONES = (
        ("CC", "CC - Cédula de ciudadanía"),  # Cédula de ciudadanía
        ("TI", "TI - Tarjeta de identidad"),  # Tarjeta de identidad
        ("RC", "RC - Registro civil"),  # Registro civil
        ("CN", "CN - Certificado de nacido vivo"),  # Certificado de nacido vivo
        ("CD", "CD - Carné diplomático"),  # Carné diplomático
        ("PA", "PA - Pasaporte"),  # Pasaporte
        ("PE", "PE - Permiso especial de pernamencia"),  # Permiso especial de pernamencia
        ("PT", "PT - Permiso por protección temporal"),  # Permiso por protección temporal
        ("SC", "SC - Salvo conducto"),  # Salvo conducto
        ("CE", "CE - Cedula de extranjería"),  # Cedula de extranjería
        ("MS", "MS - Menor sin ID"),  # Menor sin ID
        ("AS", "AS - Adulto sin ID"),  # Adulto sin ID
    )
    tipo_identificacion = forms.ChoiceField(
        choices=IDENTIFICACIONES, label='Tipo de documento',
        widget=forms.Select(attrs={'class': 'custom-select'})
    )
    identificacion = forms.CharField(
        min_length=6, max_length=20, label='Número de documento',
        widget=forms.TextInput(attrs={'class': 'effect-16', 'autofocus': True})
    )

    def clean(self):
        tipo = self.cleaned_data.get('tipo_identificacion')
        value = self.cleaned_data.get('identificacion')
        entidad = 'mutualser'
        resp = {'documento': f"{tipo}{value}"}

        if int(value) == 99_999_999:
            resp_eps = read_json('resources/fake.json')
            scrapper = ScrapMutualSer(tipo_documento=tipo, documento=value,
                                      estado='completado', resultado=resp_eps['resultado_scrapper'])
        else:
            resp_eps = obtener_datos_identificacion(entidad, tipo, value)
        validate_identificacion_exists(entidad, resp_eps, f"{tipo}{value}")
        resp_eps = resp_eps or Mutualser.get_afiliado_by_doc(tipo, value)
        validate_empty_response(resp_eps, resp['documento'], entidad)

        if int(value) == 99_999_999:
            # scrapper ha sido creado
            ...
        else:
            scrapper = ScrapMutualSer.objects.create(tipo_documento=tipo, documento=value)
            scrapper.create_or_get_and_scrap()
            validate_resp_zona_ser(scrapper)
            scrapper.load_dispensado_in_resultado()
        autorizaciones_pendientes_por_radicar = scrapper.aut_pendientes_por_disp_groub_by_nro_aut
        autorizaciones_dispensadas = scrapper.aut_dispensadas_groub_by_nro_para_facturar

        resp |= {
            'AFILIADO': resp_eps['NOMBRE'],
            'NOMBRE': f"{resp_eps['PRIMER_NOMBRE']} {resp_eps['PRIMER_APELLIDO']}",
            'P_NOMBRE': resp_eps['PRIMER_NOMBRE'],
            'TIPO_IDENTIFICACION': tipo,
            'DOCUMENTO_ID': value,
            'CONVENIO': entidad,
            'AUTORIZACIONES': autorizaciones_pendientes_por_radicar,
            'AUTORIZACIONES_DISPENSADAS': autorizaciones_dispensadas,
            'SCRAPPER_ID': scrapper.id
        }
        return resp


class AutorizacionesPorDispensar(forms.Form):
    autorizaciones = forms.CharField(widget=forms.HiddenInput(), required=False)


FORMS = [
    ("sinAutorizacion", DocumentoMutualSer),
    ("autorizacionesPorDisp", AutorizacionesPorDispensar),
    ("eligeMunicipio", EligeMunicipio),
    ("digitaDireccionBarrio", DireccionBarrio),
    ("digitaCelular", DigitaCelular),
    ("digitaCorreo", DigitaCorreo)
]


class MutualSerAutorizacion(CustomSessionWizard):
    """Clase responsable por el wizard para Mutualser."""
    # template_name = 'start.html'
    form_list = FORMS
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    post_wizard = [NotifyEmail, NotifySMS]
    template_email = BASE_DIR / "core/apps/base/templates/notifiers/correo.html"
    MANDATORIES_STEPS = ("sinAutorizacion", "autorizacionesPorDisp", "eligeMunicipio",
                         "digitaDireccionBarrio", "digitaCelular", "digitaCorreo")

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def get_form_kwargs(self, step, *args, **kwargs):
        """Pass wizard instance to forms that need access to previous step data"""
        kwargs = super().get_form_kwargs(step, *args, **kwargs)
        if step == 'digitaCelular':
            kwargs['wizard'] = self
        return kwargs

    def post(self, *args, **kwargs):
        """
        This method handles POST requests.

        The wizard will render either the current step (if form validation
        wasn't successful), the next step (if the current step was stored
        successful) or the done view (if no more steps are available)
        """
        method = self.request.method

        # Look for a wizard_goto_step element in the posted data which
        # contains a valid step name. If one was found, render the requested
        # form. (This makes stepping back a lot easier).
        wizard_goto_step = self.request.POST.get('wizard_goto_step', None)
        if wizard_goto_step and wizard_goto_step in self.get_form_list():
            # Special handling for going back from autorizacionesPorDisp to sinAutorizacion
            if self.steps.current == 'autorizacionesPorDisp' and wizard_goto_step == 'sinAutorizacion':
                # Set the current step and redirect to the URL
                self.storage.current_step = wizard_goto_step
                return HttpResponseRedirect(self.request.path)
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
            if form.prefix == "autorizacionServicio":
                self.rad_data = form.cleaned_data
            self.storage.set_step_data(self.steps.current, self.process_step(form))
            self.storage.set_step_files(self.steps.current, self.process_step_files(form))

            # check if the current step is the last step
            if self.steps.current == self.steps.last:
                # no more steps, render done view
                if not self.request.session.get('rendered_done'):
                    if res := self.render_done(form, **kwargs):
                        return res
                    else:
                        return HttpResponse(status=444)
            else:
                # proceed to the next step
                return self.render_next_step(form)
        return self.render(form)

    def render_goto_step(self, *args, **kwargs):
        """
        Es ejecutado cuando se clica en el botón "Atrás", y en caso de clicar
        en el botón "Atrás" en la vista de foto, va a resetear la variable
        new_form_list.
        :param args:
        :param kwargs:
        :return:
        """
        ls_form_list = self.form_list.keys()
        steps = list(ls_form_list)
        if (steps.index(self.steps.current) - steps.index(args[0])) != 1:
            self.request.session['ctx'] = {}
            logger.warning("redireccionando a err_multitabs por multipestañas.")
            return HttpResponseRedirect(reverse('base:err_multitabs'))

        logger.info(f"Acabó de clicar en \'< Atrás\' para ir de {self.steps.current!r} a {args[0]!r}")

        # Special handling for autorizacionesPorDisp step
        if args[0] == 'autorizacionesPorDisp':
            # Get the form with initial data from storage.extra_data
            form = self.get_form(step=args[0])
            # Ensure the form has the autorizaciones data
            if not form.initial.get('autorizaciones'):
                cached = self.storage.extra_data.get('autorizaciones', {})
                form.initial['autorizaciones'] = cached
        else:
            # Normal case: Get the form for the previous step with its stored data
            form = self.get_form(
                step=args[0],
                data=self.storage.get_step_data(args[0]),
                files=self.storage.get_step_files(args[0])
            )

        # Set the current step
        self.storage.current_step = args[0]

        # Render the form with its preserved data
        return self.render(form)

    def get_form_initial(self, step):
        """Permite mostrar la información de medicamentos por radicar en paso autorizacionesPorDisp."""
        if step == 'autorizacionesPorDisp':
            data_step_autorizacion_mutualser = self.storage.extra_data.get('autorizaciones', {})
            return {'autorizaciones': data_step_autorizacion_mutualser}
        return {}

    @once_in_interval(6)
    def render_done(self, form, **kwargs):
        """
        This method gets called when all forms passed. The method should also
        re-validate all steps to prevent manipulation. If any form fails to
        validate, `render_revalidation_failure` should get called.
        If everything is fine call `done`.
        """
        self.request.session['rendered_done'] = True
        final_forms = OrderedDict()

        # walk through the form list and try to validate the data again.
        for form_key in self.get_form_list():
            try:
                files = self.storage.get_step_files(form_key)
            except FileNotFoundError:
                logger.info(f"tmp/ -> {list(self.file_storage.base_location.iterdir())}")
                logger.info("IMAGEN ELIMINADA... NO EXISTE MAS !!!!")
                notify(
                    'error-email',
                    "EMAIL ENVIADO SIN IMAGEN",
                    "Revisa los logs de la app en heroku.",
                )

            # Get the form with stored data
            form_obj = self.get_form(
                step=form_key,
                data=self.storage.get_step_data(form_key),
                files=files
            )

            # Skip validation for forms that don't need it
            if form_key == 'sinAutorizacion':
                # For these forms, we'll use the stored data directly
                form_obj.is_valid = lambda: True
                form_obj.cleaned_data = self.storage.extra_data.get('autorizaciones')
            elif form_obj.is_valid():
                final_forms[form_key] = form_obj

            final_forms[form_key] = form_obj

        return self.done(list(final_forms.values()), form_dict=final_forms, **kwargs)

    @logtime('CORE')
    def process_from_data(self, form_list, **kwargs) -> dict:
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
        form_data = {k: v.cleaned_data for k, v in kwargs['form_dict'].items()}

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
        if not info_email.get('documento'):
            info_email |= kwargs['form_dict']['sinAutorizacion'].cleaned_data
        del info_email['cod_dane']
        del info_email['activo']
        del info_email['AUTORIZACIONES_DISPENSADAS']
        autorizaciones = info_email.pop('AUTORIZACIONES', None)
        info_email['DOCUMENTO_ID'] = info_email.pop('documento')
        for nro_aut, meds in autorizaciones.items():
            info_email['NUMERO_AUTORIZACION'] = nro_aut
            info_email['DETALLE_AUTORIZACION'] = meds
            celular = info_email.get('celular')
            if info_email.get('DOCUMENTO_ID') != 'CC99999999':
                guardar_info_bd(**info_email, ip=ip)
            info_email['celular'] = celular

            self.log_text = f"{nro_aut} {info_email['DOCUMENTO_ID']}"

            logger.info(f"{self.log_text} {info_email['NOMBRE']} Radicación finalizada. "
                        f"E-mail de confirmación será enviado a {', '.join(form_data['digitaCorreo'])}")

            # if not settings.DEBUG:
            #     En producción esto se realiza así para liberar al usuario en el front
            #     x = threading.Thread(target=self.run_post_wizard, args=(info_email, rad_id))
            #     x.start()
            # else:
            self.run_post_wizard(info_email, nro_aut)

        # Se usa NUMERO_AUTORIZACION porque es el valor que /finalizado espera
        resp = form_data['sinAutorizacion']
        resp.update({'NUMERO_AUTORIZACION': ', '.join(list(autorizaciones))})
        return resp

    def run_post_wizard(self, info_email, rad_id) -> None:
        """Ejecuta la función run de cada clase listada en post_wizard"""
        context = info_email.copy()
        context['FECHA_AUTORIZACION'] = now()  # En términos de negocio para mutual ser es más una fecha de radicación
        for step in self.post_wizard:
            check, context = step(log_text=self.log_text, template=self.template_email).proceed(context, rad_id)
            if not check:
                logger.warning(f"{step} presentó fallas al ser ejecutado.")
