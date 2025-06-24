import logging
from collections import OrderedDict

from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect
from formtools.wizard.forms import ManagementForm
from formtools.wizard.views import SessionWizardView

from core.apps.base.models import Barrio
from core.apps.base.resources.decorators import once_in_interval
from core.apps.base.resources.tools import notify
from core.settings import logger, ch


class CustomSessionWizard(SessionWizardView):
    auth_serv = {}
    foto_fmedica = None
    form_valids = OrderedDict()
    rad_data = None
    csrf_protected_method = method_decorator(csrf_protect)
    MANDATORIES_STEPS = None

    def steps_completed(self, **kwargs) -> bool:
        """Valida si todos los pasos obligatorios llegan al \'done\'"""
        return not bool(set(self.MANDATORIES_STEPS).difference(kwargs['form_dict']))

    @csrf_protected_method
    def get(self, request, *args, **kwargs):
        self.request.session['rendered_done'] = False
        sessionid = self.request.COOKIES.get('sessionid') or 'Unknown'
        source = request.GET.get('s', None)
        self.set_formatter_with_ssid() if sessionid != 'Unknown' else self.set_formatter_base()
        msg = (f"IP={self.request.META.get('HTTP_X_FORWARDED_FOR', self.request.META.get('REMOTE_ADDR'))} "
               f"entró en vista={self.request.resolver_match.url_name}/")
        if source:
            self.request.COOKIES['source'] = source
            tipo_usuario = {'f': 'fomag', 'c': 'cajacopi', 'm': 'mutualser'}
            logger.info(f"usuario {tipo_usuario[source].upper()} con {msg}")
            if source == 'm':
                logger.info(f'Redireccionando usuario {tipo_usuario[source].upper()} a /mutualser')
                return redirect('/mutualser')
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
        # logger.info(
        #     f"{self.request.COOKIES.get('sessionid')[:6]} IP={self.request.META.get('HTTP_X_FORWARDED_FOR', self.request.META.get('REMOTE_ADDR'))} "
        #     f"[{method}.{self.response_class.status_code}] "
        #     f"agent={parse_agent(self.request.META.get('HTTP_USER_AGENT'))} "
        #     f"saliendo_de={self.steps.current}")
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
            # self.form_valids[form.prefix] = form
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
        sessionid = self.request.COOKIES.get('sessionid') or 'Unknown'
        self.set_formatter_with_ssid() if sessionid != 'Unknown' else self.set_formatter_base()

        idx_view = list(self.form_list).index(self.steps.current)
        if self.steps.current != 'home':
            logger.info(f"vista{idx_view}={self.steps.current}, capturado={form.cleaned_data}")

        step = self.steps.current
        if step == 'sinAutorizacion' and form.is_valid():
            self.storage.extra_data['autorizaciones'] = form.cleaned_data
        # ls_form_list = self.form_list.keys()
        # logger.info(f"{self.request.COOKIES.get('sessionid')[:6]} Al salir de {self.steps.current} las vistas son {list(ls_form_list)}")
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
        ls_form_list = self.form_list.keys()
        steps = list(ls_form_list)
        if (steps.index(self.steps.current) - steps.index(args[0])) != 1:
            self.request.session['ctx'] = {}
            logger.warning("redireccionando a err_multitabs por multipestañas.")
            return HttpResponseRedirect(reverse('base:err_multitabs'))

        logger.info(f"Acabó de clicar en \'< Atrás\' para ir de {self.steps.current!r} a {args[0]!r}")

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
        form = super(CustomSessionWizard, self).get_form(step, data, files)
        step = step or self.steps.current
        if self.request.method == 'POST' and step == 'sinAutorizacion' and self.request.GET:
            form.source = self.request.GET.get('s', '')
        if step == 'digitaDireccionBarrio':
            if form1_cleaned_data := self.get_cleaned_data_for_step('eligeMunicipio'):
                barrios_mun = Barrio.objects.filter(
                    municipio__id=form1_cleaned_data['municipio'].id,
                    status=1
                ).order_by('name')
                form.fields['barrio'].choices = [(str(b.id), b.name.title()) for b in barrios_mun]
        return form

    @once_in_interval(6)
    def render_done(self, form, **kwargs):
        """
        This method gets called when all forms passed. The method should also
        re-validate all steps to prevent manipulation. If any form fails to
        validate, `render_revalidation_failure` should get called.
        If everything is fine call `done`.
        """
        self.request.session['rendered_done'] = True
        # logger.info(f'Entrando en render_done {CustomSessionWizard.new_form_list=}')
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

            form_obj = self.get_form(
                step=form_key,
                data=self.storage.get_step_data(form_key),
                files=files
            )
            if files:
                ...
                # Las siguientes 2 lineas fueron comentadas para ahorrar logs en papertrail
                # logger.info(f"tmp/ -> {list(self.file_storage.base_location.iterdir())}")
                # logger.info(f"files => {files}")
            if form_obj.is_valid():
                final_forms[form_key] = form_obj
                # return self.render_revalidation_failure(form_key, form_obj, **kwargs)

        # self.storage.reset()
        return self.done(list(final_forms.values()), form_dict=final_forms, **kwargs)

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

    def process_from_data(self, form_list, **kwargs):
        raise NotImplementedError(
            f"Your {self.__class__.__name__} class has not defined a process_from_data() method, which is required."
        )

    def get_form_step_files(self, form):
        """
        Is used to return the raw form files. You may use this method to
        manipulate the data.
        """
        if form.prefix == 'fotoFormulaMedica':
            from datetime import datetime
            try:
                ext = f".{form.files['fotoFormulaMedica-src'].image.format.lower()}"
                name = f'{datetime.now():%d%m%Y%H%M%S%s}'[:16]
                form.files['fotoFormulaMedica-src'].name = name + ext
            except KeyError as e:
                logger.error(f"No fue encontrado 'fotoFormulaMedica-src' en form.files : {str(e)}")
            except Exception as e:
                logger.error(str(e))

        return form.files

    def set_formatter_with_ssid(self):
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(ssid)s %(message)s", "[%d/%b/%Y %H:%M:%S]",
                              defaults={"ssid": f"[{self.request.COOKIES.get('sessionid')[:6]}]"})
        formatter._my_ssid = f"{self.request.COOKIES.get('sessionid')[:6]}"
        ch.setFormatter(formatter)

    def set_formatter_base(self):
        ch.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                              "[%d/%b/%Y %H:%M:%S]")
        )
