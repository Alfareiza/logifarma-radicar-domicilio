import json
import shutil

from django.core.files.storage import FileSystemStorage
from django.core.mail import EmailMessage
from django.shortcuts import render
from formtools.wizard.views import SessionWizardView

from core import settings
from core.apps.base.forms import *
from core.apps.base.resources.tools import convert_bytes
from core.settings import logger

FORMS = [
    ("home", Home),
    ("instrucciones", Instrucciones),
    ("autorizacionServicio", AutorizacionServicio),
    ("fotoFormulaMedica", FotoFormulaMedica),
    ("avisoDireccion", AvisoDireccion),
    ("eligeMunicipio", EligeMunicipio),
    ("eligeBarrio", EligeBarrio),
    ("digitaDireccion", DigitaDireccion),
    ("digitaCelular", DigitaCelular)
]

TEMPLATES = {
    "home": "home.html",
    "instrucciones": "instrucciones.html",
    "autorizacionServicio": "autorizacion.html",
    "fotoFormulaMedica": "foto.html",
    "avisoDireccion": "aviso_direccion.html",
    "eligeMunicipio": "elige_municipio.html",
    "eligeBarrio": "elige_barrio.html",
    "digitaDireccion": "digita_direccion.html",
    "digitaCelular": "digita_celular.html"}


class ContactWizard(SessionWizardView):
    # template_name = 'start.html'
    form_list = FORMS
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)

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
        # logger.info(self.get_form_step_data(form))
        return self.get_form_step_data(form)

    def render_goto_step(self, *args, **kwargs):
        form = self.get_form(data=self.request.POST, files=self.request.FILES)
        self.storage.set_step_data(self.steps.current, self.process_step(form))
        self.storage.set_step_files(self.steps.first, self.process_step_files(form))
        return super().render_goto_step(*args, **kwargs)

    def done(self, form_list, **kwargs):
        form_data = self.process_from_data(form_list)
        for i, param in enumerate(form_list, 1):
            if param:
                logger.info(f'=> {i}. {param.cleaned_data}')
        return render(self.request,
                      'done.html',
                      context={'form_data': form_data}
                      )

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
        # logger.info(f"RESP_API={form_data[2]['num_autorizacion']}")

        # Crea y guarda imagen en settings.MEDIA_ROOT
        self.contentfile_to_img(contentfile_obj=form_data[3]['src'])
        # Envía e-mail
        self.send_mail(name=form_data[2]['num_autorizacion']['AFILIADO'],
                       body=form_data[2]['num_autorizacion'],
                       destinatary=form_data[2]['num_autorizacion']['CORREO_TEST'])

    def send_mail(self, name: str, destinatary: str, body: str):
        """
        Envía email con imagen adjunta.
        :param name: Nombre del afiliado.
        :param destinatary: Email del afiliado
        :return: None
        """
        email = EmailMessage(subject='Este es el asunto del correo',
                             body=f"Hola, Sr(a) {name}\n\nLe estamos enviando este mensaje:\n"
                                  f"{json.dumps(body, indent=2)}",
                             from_email=settings.EMAIL_HOST_USER, to=destinatary,
                             bcc=['alfareiza@gmail.com']
                             )

        email.attach_file(self.foto_fmedica)
        try:
            email.send(fail_silently=False)
            logger.info(f'Correo enviado a \"{destinatary}\" con imagen '
                        f'adjunta de {convert_bytes(self.foto_fmedica.stat().st_size)}')
        except Exception as e:
            logger.error('Error al enviar el correo ', e)
            # Si hubo error se puede implementar el envío de otro
            # email avisando de este error.
        finally:
            self.del_folder(settings.MEDIA_ROOT)

    def contentfile_to_img(self, contentfile_obj):
        """
        Convierte la imagem de ContentFile a una imagen como tal
        y la guarda en la carpeta MEDIA_ROOT.
        :param contentfile_obj: <ContentFile: Raw content>
                type(contentfile_obj) -> django.core.files.base.ContentFile
                contentfile_obj.__dict__ -> {'file': <_io.BytesIO at 0x7fd2750425e0>,
                                             'name': 'formula_medica.png', 'size': 139049}
        :return: None
        """
        foto_fmedica = ContactWizard.file_storage.save(
            contentfile_obj.name, contentfile_obj.file
        )
        self.foto_fmedica = settings.MEDIA_ROOT / foto_fmedica

    def del_folder(self, MEDIA_ROOT):
        """
        Elimina la carpeta donde se guardó la imagen y
        lo que en ella se encuentre.
        :param MEDIA_ROOT: 'tmp_logifrm/formula_medica.png'
        :return: None
        """
        try:
            shutil.rmtree(MEDIA_ROOT)
        except FileNotFoundError as e:
            logger.error('Error al borrar la carpeta: ', e)
