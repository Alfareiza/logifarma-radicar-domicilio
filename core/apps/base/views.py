from collections import OrderedDict

from django.core.files.storage import FileSystemStorage
from django.core.mail import EmailMessage
from django.shortcuts import render
from django.template.loader import get_template
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from formtools.wizard.views import SessionWizardView

from core import settings
from core.apps.base.forms import *
from core.apps.base.models import Barrio
from core.apps.base.resources.tools import convert_bytes, del_file, parse_agent
from core.settings import logger, BASE_DIR

FORMS = [
    ("home", Home),
    ("instrucciones", Instrucciones),
    ("autorizacionServicio", AutorizacionServicio),
    ("fotoFormulaMedica", FotoFormulaMedica),
    ("avisoDireccion", AvisoDireccion),
    ("eligeMunicipio", EligeMunicipio),
    ("digitaDireccionBarrio", DireccionBarrio),
    ("digitaCelular", DigitaCelular),
    ("digitaCorreo", DigitaCorreo)
]

TEMPLATES = {
    "home": "home.html",
    "instrucciones": "instrucciones.html",
    "autorizacionServicio": "autorizacion.html",
    "fotoFormulaMedica": "foto.html",
    "avisoDireccion": "aviso_direccion.html",
    "eligeMunicipio": "elige_municipio.html",
    "digitaDireccionBarrio": "direccion_barrio.html",
    "digitaCelular": "digita_celular.html",
    "digitaCorreo": "digita_correo.html"}

htmly = get_template(BASE_DIR / "core/apps/base/templates/correo.html")


class ContactWizard(SessionWizardView):
    # template_name = 'start.html'
    form_list = FORMS
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)

    csrf_protected_method = method_decorator(csrf_protect)

    @csrf_protected_method
    def get(self, request, *args, **kwargs):
        logger.info(f"IP={self.request.META.get('REMOTE_ADDR')} "
                    f"entró en vista={self.request.resolver_match.url_name}")
        return super().get(request, *args, **kwargs)

    @csrf_protected_method
    def post(self, *args, **kwargs):
        method = self.request.method
        logger.info(
            "IP={} [{}.{}] agent={}  saliendo de={}; ".format(
                # self.request.COOKIES.get('sessionid'),
                self.request.META.get('REMOTE_ADDR'),
                method, self.response_class.status_code,
                parse_agent(self.request.META.get('HTTP_USER_AGENT')),
                # self.request.META.get('HTTP_ORIGIN'),
                self.steps.current,
            ))
        return super().post(*args, **kwargs)

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def process_step(self, form):
        """
        Se ejecuta al hacer el post del current step.
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
        logger.info(f"vista{idx_view}={self.steps.current}, capturado={form.cleaned_data}")
        return self.get_form_step_data(form)

    def render_goto_step(self, *args, **kwargs):
        form = self.get_form(data=self.request.POST, files=self.request.FILES)
        # self.storage.set_step_data(self.steps.current, self.process_step(form))
        self.storage.set_step_files(self.steps.first, self.process_step_files(form))
        return super().render_goto_step(*args, **kwargs)

    def done(self, form_list, **kwargs):
        form_data = self.process_from_data(form_list)
        return render(self.request,
                      'done.html',
                      context={'form_data': form_data}
                      )

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
        form = super(ContactWizard, self).get_form(step, data, files)
        step = step or self.steps.current
        if step == 'digitaDireccionBarrio':
            if form1_cleaned_data := self.get_cleaned_data_for_step('eligeMunicipio'):
                barrios_mun = Barrio.objects.filter(
                    municipio__id=form1_cleaned_data['municipio'].id
                ).order_by('name')
                form.fields['barrio'].choices = [(str(b.id), b.name.title()) for b in barrios_mun]
                form.fields['barrio'].choices.insert(0, ('X', 'Seleccione el barrio'))
        return form

    def process_from_data(self, form_list):
        """
        Se encarga de crear y guardar imagen, y luego envía el correo
        a partir de algunos datos de la API de la EPS.
        - form_data[2] posee la información de la API de la EPS
        - form_data[3] posee la información de la imagen
        :param form_list: List de diccionarios donde cada index es el
                          resultado de lo capturado en cada formulario.
                          Cada key es el declarado en cada form.
        :return: None.
                En caso de querer mostrar alguna información en el done.html
                se debe retonar en esta función.
        """
        form_data = [form.cleaned_data for form in form_list]

        self.foto_fmedica = form_data[3]['src']

        # Construye las variables que serán enviadas al template
        info_email = {
            **form_data[2]['num_autorizacion'],
            **form_data[5],  # Ciudad
            **form_data[6],  # Barrio y dirección
            **form_data[7],  # Celular
            **form_data[8],  # e-mail
        }

        logger.info('E-mail será enviado con la siguiente información : ')

        for log in info_email:
            logger.info(f'== {log} ==> {info_email[log]}')

        body = htmly.render(info_email)

        asunto = f"{info_email['NUMERO_AUTORIZACION']} - Este es el " \
                 f"número de radicación de tu domicilio en Logifarma"

        if info_email['NUMERO_AUTORIZACION'] == 99_999_999:
            asunto = '[OMITIR] CORREO DE PRUEBA'

        # Envía e-mail
        self.send_mail(
            subject=asunto,
            destinatary=[info_email['email']],
            html_content=body
        )

    def send_mail(self, subject: str, destinatary: str, html_content):
        """
        Envía email con imagen adjunta.
        :param name: Nombre del afiliado.
        :param destinatary: Email del afiliado
        :return: None
        """
        email = EmailMessage(
            subject, html_content,
            from_email=f"Domicilios Logifarma <{settings.EMAIL_HOST_USER}>",
            to=destinatary,
            bcc=config('EMAIL_BCC', cast=Csv())
        )
        email.content_subtype = "html"
        try:
            email.attach_file(self.foto_fmedica.file.file.name)
            r = email.send(fail_silently=False)
            print(r)
            logger.info(f'Correo enviado a {destinatary} con imagen '
                        f'adjunta de {convert_bytes(self.foto_fmedica.file.size)}')
        except Exception as e:
            logger.error('Error al enviar el correo ', e)
            # Si hubo error se puede implementar el envío de otro
            # email avisando de este error.
        finally:
            del_file(self.foto_fmedica.file.file.name)

    # def contentfile_to_img(self, contentfile_obj):
    #     """
    #     Convierte la imagem de ContentFile a una imagen como tal
    #     y la guarda en la carpeta MEDIA_ROOT.
    #     :param contentfile_obj: <ContentFile: Raw content>
    #             type(contentfile_obj) -> django.core.files.base.ContentFile
    #             contentfile_obj.__dict__ -> {'file': <_io.BytesIO at 0x7fd2750425e0>,
    #                                          'name': 'formula_medica.png', 'size': 139049}
    #     :return: None
    #     """
    #     foto_fmedica = ContactWizard.file_storage.save(
    #         contentfile_obj.name, contentfile_obj.file
    #     )
    #     self.foto_fmedica = settings.MEDIA_ROOT / foto_fmedica

    def render_done(self, form, **kwargs):
        """
        | Función sobrescrita y comentando la linea de self.storage.reset() |
        This method gets called when all forms passed. The method should also
        re-validate all steps to prevent manipulation. If any form fails to
        validate, `render_revalidation_failure` should get called.
        If everything is fine call `done`.
        """
        final_forms = OrderedDict()
        # walk through the form list and try to validate the data again.
        for form_key in self.get_form_list():
            form_obj = self.get_form(
                step=form_key,
                data=self.storage.get_step_data(form_key),
                files=self.storage.get_step_files(form_key)
            )
            if not form_obj.is_valid():
                return self.render_revalidation_failure(form_key, form_obj, **kwargs)
            final_forms[form_key] = form_obj

        # render the done view and reset the wizard before returning the
        # response. This is needed to prevent from rendering done with the
        # same data twice.
        # self.storage.reset()
        return self.done(list(final_forms.values()), form_dict=final_forms, **kwargs)
