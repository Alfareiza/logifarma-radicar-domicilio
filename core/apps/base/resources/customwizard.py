from collections import OrderedDict

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from formtools.wizard.views import SessionWizardView

from core.apps.base.models import Barrio
from core.apps.base.resources.tools import parse_agent
from core.settings import logger


class CustomSessionWizard(SessionWizardView):
    new_form_list = OrderedDict()
    auth_serv = {}
    foto_fmedica = None

    csrf_protected_method = method_decorator(csrf_protect)

    @csrf_protected_method
    def get(self, request, *args, **kwargs):
        logger.info(f"IP={self.request.META.get('HTTP_X_FORWARDED_FOR', 'NO_IP_DETECTED')} "
                    f"entró en vista={self.request.resolver_match.url_name}")
        return super().get(request, *args, **kwargs)

    @csrf_protected_method
    def post(self, *args, **kwargs):
        method = self.request.method
        logger.info(f"IP={self.request.META.get('HTTP_X_FORWARDED_FOR', 'NO_IP_DETECTED')} "
                    f"[{method}.{self.response_class.status_code}] "
                    f"agent={parse_agent(self.request.META.get('HTTP_USER_AGENT'))} "
                    f"saliendo_de={self.steps.current}")

        return super().post(*args, **kwargs)

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
            logger.info(f"No fue capturado nada en vista{idx_view}={self.steps.current}")
        else:
            logger.info(f"vista{idx_view}={self.steps.current}, capturado={form.cleaned_data}")
            if self.steps.current == 'autorizacionServicio':
                self.auth_serv = form.cleaned_data

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
        if 'autorizacionServicio' in args:
            CustomSessionWizard.new_form_list.clear()
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
        if step == 'digitaDireccionBarrio':
            if form1_cleaned_data := self.get_cleaned_data_for_step('eligeMunicipio'):
                barrios_mun = Barrio.objects.filter(
                    municipio__id=form1_cleaned_data['municipio'].id
                ).order_by('name')
                form.fields['barrio'].choices = [(str(b.id), b.name.title()) for b in barrios_mun]
        return form

    def render_done(self, form, **kwargs):
        """
        | Función sobrescrita y comentando la linea de self.storage.reset() |
        This method gets called when all forms passed. The method should also
        re-validate all steps to prevent manipulation. If any form fails to
        validate, `render_revalidation_failure` should get called.
        If everything is fine call `done`.
        """

        # final_forms = OrderedDict()
        # walk through the form list and try to validate the data again.
        for form_key in CustomSessionWizard.new_form_list:
            form_obj = self.get_form(
                step=form_key,
                data=self.storage.get_step_data(form_key),
                files=self.storage.get_step_files(form_key)
            )
            # TODO Evitar validar todos los formularios al finalizar el wizard
            if not form_obj.is_valid():
                return self.render_revalidation_failure(form_key, form_obj, **kwargs)
            CustomSessionWizard.new_form_list[form_key] = form_obj

        # render the done view and reset the wizard before returning the
        # response. This is needed to prevent from rendering done with the
        # same data twice.
        # self.storage.reset()
        return self.done(list(CustomSessionWizard.new_form_list.values()),
                         form_dict=CustomSessionWizard.new_form_list,
                         **kwargs)

    def get_form_list(self):
        """
        This method returns a form_list based on the initial form list but
        checks if there is a condition method/value in the condition_list.
        If an entry exists in the condition list, it will call/read the value
        and respect the result. (True means add the form, False means ignore
        the form)

        The form_list is always generated on the fly because condition methods
        could use data from other (maybe previous forms).
        """
        if len(CustomSessionWizard.new_form_list) > 0:
            return CustomSessionWizard.new_form_list

        if all((self.auth_serv, self.storage.current_step == 'autorizacionServicio')):
            for count, (form_key, form_class) in enumerate(self.form_list.items(), start=1):
                condition = self.condition_dict.get(form_key, True)
                if callable(condition) and condition.__name__ == 'show_fotoFormulaMedica':
                    condition = condition(self.auth_serv)
                if condition:
                    CustomSessionWizard.new_form_list[form_key] = form_class
            return CustomSessionWizard.new_form_list
        return self.form_list
