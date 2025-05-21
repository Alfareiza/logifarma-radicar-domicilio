import os
import threading
from collections import OrderedDict
from importlib import import_module

import undetected_chromedriver as uc
from django import http
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.storage import DefaultStorage
from django.http import HttpResponseRedirect
from django.urls import reverse
from formtools.wizard.views import WizardView
from selenium.webdriver import Keys, ActionChains
from selenium.webdriver.common.by import By

from core.apps.base.forms import Home, AutorizacionServicio, FotoFormulaMedica, \
    EligeMunicipio, DireccionBarrio, DigitaCelular, DigitaCorreo
from core.apps.base.models import Municipio, Barrio
from core.apps.base.pipelines import NotifyEmail, NotifySMS, Drive, UpdateDB
from core.apps.base.resources.decorators import logtime
from core.apps.base.resources.img_helpers import ImgHelper
from core.apps.base.resources.tools import guardar_short_info_bd
from core.apps.base.views import FORMS
from core.apps.base.views import TEMPLATES
from core.settings import BASE_DIR, logger

os.environ["PATH"] += f'{os.pathsep}/usr/local/bin'
MANDATORIES_STEPS_SIN_AUTORIZACION = ("sinAutorizacion", "eligeMunicipio",
                                      "digitaDireccionBarrio", "digitaCelular", "digitaCorreo")


class VisualWizardTests(StaticLiveServerTestCase):
    vistas = [ele[0] for ele in FORMS]
    map_vistas = [
        {'Domicilios Logifarma': 'self.process_home()'},
        {'Autorización de servicio': "self.process_autorizacion()"},
        {'Foto de la fórmula': 'self.process_foto()'},
        {'Elige Municipio': 'self.process_elige_municipio()'},
        {'Elige el barrio': 'self.process_direccion_barrio()'},
        {'Digite celular': 'self.process_celular()'},
        {'Digite un correo electrónico': 'self.process_correo()'},
        {'Listo': 'self.process_correo()'},
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # options = Options()
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument("--window-size=1920,1200")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('disable-infobars')
        options.add_argument('--disable-extensions')
        cls.selenium = uc.Chrome(
            # service=Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()),
            options=options,
            version_main=111
        )
        cls.selenium.maximize_window()
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def get_btn(self, type, value):
        btn = None
        if type == 'class':
            btn = self.selenium.find_element(by=By.CLASS_NAME, value=value)
        elif type == 'id':
            btn = self.selenium.find_element(by=By.ID, value=value)
        elif type == 'name':
            btn = self.selenium.find_element(by=By.NAME, value=value)
        return btn

    def get_boton_continuar(self, value='btn'):
        return self.get_btn('class', value)

    def get_animacion(self, value='btn_carga'):
        return self.get_btn('id', value)

    def get_boton_atras(self, value='atras'):
        return self.get_btn('class', value)

    def insert_data(self, **kwargs):
        num_aut_box = self.get_btn('name', kwargs.get('value'))
        num_aut_box.send_keys(kwargs.get('data'))
        return num_aut_box

    def animacion_works(self, animacion, id_btn='btn_conti'):
        self.selenium.execute_script(f'document.getElementById("{id_btn}").click(); window.stop()')
        works = animacion.value_of_css_property('display') == 'block'
        self.selenium.execute_script('window.location.reload()')
        return works

    def process_home(self):
        self.selenium.execute_script("window.scrollTo(0,document.body.scrollHeight)")
        self.get_boton_continuar('btn_inicio').click()

    def process_instrucciones(self):
        self.get_boton_continuar().click()
        if self.selenium.title != 'Autorización de servicio':
            self.take_me_to_the_step('autorizacionServicio')

    def process_autorizacion(self, number='99999999', expected_step=('Foto de la fórmula', 'fotoFormulaMedica')):
        mun, _ = Municipio.objects.get_or_create(name='barranquilla', departamento='atlántico')
        Barrio.objects.get_or_create(name='el recreo', municipio=mun, zona='norte',
                                     cod_zona=109, status=1)
        Barrio.objects.get_or_create(name='cevillar', municipio=mun, zona='sur',
                                     cod_zona=109, status=1)
        Barrio.objects.get_or_create(name='adelita de char', municipio=mun, zona='norte',
                                     cod_zona=109, status=1)
        num_aut_box = self.insert_data(value="autorizacionServicio-num_autorizacion", data=number)
        num_aut_box.send_keys(Keys.ENTER)
        if self.selenium.title != expected_step[0]:
            self.take_me_to_the_step(expected_step[1])

    def process_foto(self):
        img = BASE_DIR / 'core/apps/base/tests/resources/image_1.jpg'
        self.selenium.find_element(by=By.ID, value='id_fotoFormulaMedica-src').send_keys(str(img))

        self.get_boton_continuar().click()
        if self.selenium.title != 'Elige Municipio':
            self.take_me_to_the_step('eligeMunicipio')

    def process_elige_municipio(self):
        self.selenium.find_element(by=By.CLASS_NAME, value='con').click()
        self.get_boton_continuar().click()
        if self.selenium.title != 'Elige el barrio':
            self.take_me_to_the_step('digitaDireccionBarrio')

    def process_direccion_barrio(self):
        self.insert_data(value="digitaDireccionBarrio-direccion", data='CUALQUIER DIRECCIÓN')
        ActionChains(self.selenium).send_keys(Keys.TAB).perform()
        ActionChains(self.selenium).send_keys(Keys.TAB).perform()
        ActionChains(self.selenium).send_keys(Keys.SPACE).perform()
        ActionChains(self.selenium).send_keys(Keys.TAB).perform()
        ActionChains(self.selenium).send_keys(Keys.SPACE).perform()
        # self.get_boton_continuar().click()
        if self.selenium.title != 'Digite celular':
            self.take_me_to_the_step('digitaCelular')

    def process_celular(self):
        self.insert_data(value="digitaCelular-celular", data='3000000000')
        self.get_boton_continuar().click()
        if self.selenium.title != 'Digite un correo electrónico':
            self.take_me_to_the_step('digitaCorreo')

    def process_correo(self):
        self.insert_data(value="digitaCorreo-email", data='jane@doe.com')
        self.get_boton_continuar().click()
        if self.selenium.title != 'Listo':
            self.take_me_to_the_step('digitaCorreo')
            self.get_boton_continuar().click()

    def process_finalizado(self):
        self.get_boton_continuar().click()
        if self.selenium.title != 'Domicilios Logifarma':
            self.take_me_to_the_step('digitaCorreo')
            self.get_boton_continuar().click()
            self.get_boton_continuar().click()

    def take_me_to_the_step(self, to_step):
        current = [i for i, v in enumerate(self.map_vistas) if list(v.keys()) == [self.selenium.title]]
        desde = current[0]
        hasta = self.vistas.index(to_step)
        # print(f"Al querer avanzar a {to_step}, fue llevado a {self.selenium.title}")
        if hasta - desde == 1:
            eval(list(self.map_vistas[desde].values())[0])
        else:
            # print(f'Voy a ir de {self.vistas[desde]} a {to_step}')
            for vista in self.map_vistas[desde:hasta]:
                print('Exec ->', list(vista.values())[0])
                eval(list(vista.values())[0])


class DummyRequest(http.HttpRequest):
    def __init__(self, POST=None):
        super().__init__()
        self.method = "POST" if POST else "GET"
        if POST is not None:
            self.POST.update(POST)
        self.session = {}
        self._dont_enforce_csrf_checks = True


def get_request(*args, **kwargs):
    request = DummyRequest(*args, **kwargs)
    engine = import_module(settings.SESSION_ENGINE)
    request.session = engine.SessionStore(None)
    return request


class TestWizard(WizardView):
    storage_name = 'formtools.wizard.storage.session.SessionStorage'
    file_storage = DefaultStorage()

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        return response, self

    def get_form_kwargs(self, step, *args, **kwargs):
        kwargs = super().get_form_kwargs(step, *args, **kwargs)
        if step == 'kwargs_test':
            kwargs['test'] = True
        return kwargs

    def get_form(self, step=None, data=None, files=None):
        form = super(TestWizard, self).get_form(step, data, files)
        step = step or self.steps.current
        if step == 'digitaDireccionBarrio':
            if form1_cleaned_data := self.get_cleaned_data_for_step('eligeMunicipio'):
                barrios_mun = Barrio.objects.filter(
                    municipio__id=form1_cleaned_data['municipio'].id
                ).order_by('name')
                form.fields['barrio'].choices = [(str(b.id), b.name.title()) for b in barrios_mun]
                form.fields['barrio'].choices.insert(0, ('X', 'Seleccione el barrio'))
        return form

    def render_done(self, form, **kwargs):
        """
        This method gets called when all forms passed. The method should also
        re-validate all steps to prevent manipulation. If any form fails to
        validate, `render_revalidation_failure` should get called.
        If everything is fine call `done`.
        """

        # logger.info(f'Entrando en render_done {CustomSessionWizard.new_form_list=}')
        final_forms = OrderedDict()
        # walk through the form list and try to validate the data again.
        for form_key in self.get_form_list():
            files = self.storage.get_step_files(form_key)
            form_obj = self.get_form(
                step=form_key,
                data=self.storage.get_step_data(form_key),
                files=files
            )
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
        logger.warning(f"redireccionando a err_multitabs por multipestañas.")
        return HttpResponseRedirect(reverse('base:err_multitabs'))

    def steps_completed(self, **kwargs) -> bool:
        """Valida si todos los pasos obligatorios llegan al \'done\'"""
        return not bool(set(MANDATORIES_STEPS).difference(kwargs['form_dict']))

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

        # Construye las variables que serán enviadas al template
        info_email = {
            **form_data['autorizacionServicio']['num_autorizacion'],
            **form_data['eligeMunicipio'],
            **form_data['digitaDireccionBarrio'],
            **form_data['digitaCelular'],
            'email': [*form_data['digitaCorreo']]
        }

        return form_data['autorizacionServicio']['num_autorizacion']


vistas = [Home, AutorizacionServicio, FotoFormulaMedica,
          EligeMunicipio, DireccionBarrio, DigitaCelular,
          DigitaCorreo]


class TestWizardWithInitAttrs(TestWizard):
    form_list = vistas


class TestWizardSinAutorizacion(TestWizard):
    post_wizard = [NotifyEmail, NotifySMS, Drive, UpdateDB]

    def get_template_names(self) -> list:
        return [TEMPLATES[self.steps.current]]

    def steps_completed(self, **kwargs) -> bool:
        """Valida si todos los pasos obligatorios llegan al \'done\'"""
        return not bool(set(MANDATORIES_STEPS_SIN_AUTORIZACION).difference(kwargs['form_dict']))

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
            info_email.update({'foto': self.foto_fmedica})

        rad = guardar_short_info_bd(**info_email, ip='0.0.0.0')
        info_email['ref_id'], info_email['NUMERO_RADICACION'], info_email['FECHA_RADICACION'] = rad
        rad_id = info_email['NUMERO_RADICACION']

        info_email.update({'log_text': '... ...'})

        # if not settings.DEBUG:
        # En producción esto se realiza así para liberar al usuario en el front
        # x = threading.Thread(target=self.run_post_wizard, args=(info_email, rad_id))
        # x.start()
        # else:
        self.run_post_wizard(info_email, rad_id)

        resp = form_data['sinAutorizacion']
        resp.update({'NUMERO_AUTORIZACION': rad_id})
        return resp

    def run_post_wizard(self, info_email: dict, rad_id: str) -> None:
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
        """
        Trata imagen disminuyendo su peso y conviertiéndola a blanco y negro.
        :param filepath_img: Ruta de imagen.
        """
        img = ImgHelper(filepath_img)
        img.convert_to_grayscale()
        img.save(filepath_img)
