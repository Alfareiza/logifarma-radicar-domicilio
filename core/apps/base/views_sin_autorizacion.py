from django.core.files.storage import FileSystemStorage

from core import settings
from core.apps.base.forms import *
from core.apps.base.pipelines import NotifyEmail, NotifySMS, Drive, UpdateDB
from core.apps.base.resources.customwizard import CustomSessionWizard
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.img_helpers import ImgHelper
from core.apps.base.resources.tools import guardar_short_info_bd
from core.apps.base.views import TEMPLATES
from core.settings import logger

FORMS = [
    ("sinAutorizacion", SinAutorizacion),
    ("orden", Orden),
    ("fotoFormulaMedica", FotoFormulaMedica),
    ("eligeMunicipio", EligeMunicipio),
    ("digitaDireccionBarrio", DireccionBarrio),
    ("digitaCelular", DigitaCelular),
    ("digitaCorreo", DigitaCorreo)
]


def show_orden(wizard) -> bool:
    """El paso orden siempre es mostrado con bease en el valor 'm' extraido de la URL."""
    query = wizard.request.get_full_path()
    parts = query.rsplit('=')
    return len(parts) == 2 and parts[1] == 'm'


class SinAutorizacion(CustomSessionWizard):
    # template_name = 'start.html'
    condition_dict = {'orden': show_orden}
    form_list = FORMS
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    post_wizard = [NotifyEmail, NotifySMS, Drive, UpdateDB]
    MANDATORIES_STEPS = ("sinAutorizacion", "eligeMunicipio",
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
        # form_data = [form.cleaned_data for form in form_list]
        form_data = {k: v.cleaned_data for k, v in kwargs['form_dict'].items()}

        # Construye las variables que serán enviadas al template
        info_email = {
            **form_data['sinAutorizacion'],
            **form_data['eligeMunicipio'],
            **form_data['digitaDireccionBarrio'],
            **form_data['digitaCelular'],
            **form_data.get('orden', {}),
            'email': [*form_data['digitaCorreo']]
        }

        if 'fotoFormulaMedica' in form_data:
            self.foto_fmedica = form_data['fotoFormulaMedica']['src']
            info_email['foto'] = self.foto_fmedica

        # Guardará en BD cuando DEBUG sean números reales
        ip = self.request.META.get('HTTP_X_FORWARDED_FOR', self.request.META.get('REMOTE_ADDR'))

        if info_email['documento'][2:] not in ('99999999',):
            # if True:  # Testando inserción en producción temporalmente
            rad = guardar_short_info_bd(**info_email, ip=ip)
            info_email['ref_id'], info_email['NUMERO_RADICACION'], info_email['FECHA_RADICACION'] = rad
            if info_email.get('CONVENIO', '') in ('mutualser',):
                # En mutual ser, el NUMERO_RADICACION es el mismo NUMERO_AUTORIZACION digitado por usuario
                info_email['NUMERO_RADICACION'] = info_email['ref_id']
            rad_id = info_email['NUMERO_RADICACION']  # id en db
        else:
            rad_id = '1'
            info_email['NUMERO_RADICACION'] = rad_id

        if rad_id:
            self.log_text = f"{rad_id} {info_email['documento']}"
            info_email['log_text'] = self.log_text

            logger.info(f"{self.log_text} {info_email['NOMBRE']} Radicación finalizada. "
                        f"E-mail de confirmación será enviado a {form_data['digitaCorreo']}")

            # if not settings.DEBUG:
            #     En producción esto se realiza así para liberar al usuario en el front
            # x = threading.Thread(target=self.run_post_wizard, args=(info_email, rad_id))
            # x.start()
            # else:
            self.run_post_wizard(info_email, rad_id)

        # Se usa NUMERO_AUTORIZACION porque es el valor que /finalizado espera
        resp = form_data['sinAutorizacion']
        resp.update({'NUMERO_AUTORIZACION': rad_id})
        return resp

    def run_post_wizard(self, info_email, rad_id) -> None:
        """Ejecuta la función run de cada clase listada en post_wizard"""

        # Substituye imagen existente con imagen más leve y B&W
        if self.foto_fmedica:
            self.treat_img(self.foto_fmedica.file.name)

        result = []
        for step in self.post_wizard:
            check, info_email = step().proceed(info_email, rad_id)
            if not check:
                logger.warning(f"{step} presentó fallas al ser ejecutado.")
        result.extend(info_email)

        return result

    # @logtime('IMG CONVERT')
    def treat_img(self, filepath_img: str) -> None:
        """Trata imagen disminuyendo su peso y conviertiéndola a blanco y negro.
        Posteriormente queda guardada en substitución de la imagen referenciada
        en la ruta recibida como argumento.
        :param filepath_img: Ruta de imagen.
        """
        try:
            img = ImgHelper(filepath_img)
            img.convert_to_grayscale()
            img.save(filepath_img)
        except Exception as e:
            logger.error(f"{self.log_text} {filepath_img} no pudo ser tratada por error: {e}")
