from django.core.files.storage import FileSystemStorage
from django.http import HttpResponseRedirect
from django.template.loader import get_template
from django.urls import reverse

from core import settings
from core.apps.base.forms import *
from core.apps.base.pipelines import NotifyEmail, NotifySMS, Drive, UpdateDB
from core.apps.base.resources.customwizard import CustomSessionWizard
from core.apps.base.views import TEMPLATES
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.img_helpers import ImgHelper
from core.apps.base.resources.tools import guardar_short_info_bd
from core.settings import logger, BASE_DIR

FORMS = [
    ("sinAutorizacion", SinAutorizacion),
    ("fotoFormulaMedica", FotoFormulaMedica),
    ("eligeMunicipio", EligeMunicipio),
    ("digitaDireccionBarrio", DireccionBarrio),
    ("digitaCelular", DigitaCelular),
    ("digitaCorreo", DigitaCorreo)
]

MANDATORIES_STEPS_SIN_AUTORIZACION = ("sinAutorizacion", "eligeMunicipio",
                                      "digitaDireccionBarrio", "digitaCelular", "digitaCorreo")

htmly = get_template(BASE_DIR / "core/apps/base/templates/notifiers/correo_sin_autorizacion.html")


class SinAutorizacion(CustomSessionWizard):
    # template_name = 'start.html'
    form_list = FORMS
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    post_wizard = [NotifyEmail, NotifySMS, Drive, UpdateDB]

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
        return not bool(set(MANDATORIES_STEPS_SIN_AUTORIZACION).difference(kwargs['form_dict']))

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
            rad_id = info_email['NUMERO_RADICACION']
        else:
            rad_id = '1'
            info_email['NUMERO_RADICACION'] = rad_id

        if rad_id:
            self.log_text = f"{self.request.COOKIES.get('sessionid')[:6]} {rad_id=} {info_email['documento']}"
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

    @staticmethod
    @logtime('IMG CONVERT')
    def treat_img(filepath_img: str) -> None:
        """Trata imagen disminuyendo su peso y conviertiéndola a blanco y negro.
        Posteriormente queda guardada en substitución de la imagen referenciada
        en la ruta recibida como argumento.
        :param filepath_img: Ruta de imagen.
        """
        try:
            img = ImgHelper(filepath_img)
        except Exception as e:
            logger.warning(f"{filepath_img} no pudo ser tratada por error: {e}p")
        else:
            img.convert_to_grayscale()
            img.save(filepath_img)
