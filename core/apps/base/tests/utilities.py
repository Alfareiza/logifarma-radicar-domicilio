from importlib import import_module

from django import http
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.storage import DefaultStorage
from django.shortcuts import render
from formtools.wizard.views import WizardView
from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.utils import ChromeType

from core.apps.base.forms import Home, Instrucciones, AutorizacionServicio, FotoFormulaMedica, AvisoDireccion, \
    EligeMunicipio, DireccionBarrio, DigitaCelular, DigitaCorreo
from core.apps.base.models import Municipio, Barrio
from core.apps.base.views import FORMS, TEMPLATES
from core.settings import BASE_DIR


class VisualWizardTests(StaticLiveServerTestCase):
    vistas = [ele[0] for ele in FORMS]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('disable-infobars')
        options.add_argument('--disable-extensions')
        cls.selenium = webdriver.Chrome(
            service=Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()),
            options=options
        )
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def get_boton_continuar(self):
        return self.selenium.find_element(by=By.CLASS_NAME, value='btn')

    def get_animacion(self):
        return self.selenium.find_element(by=By.ID, value='btn_carga')

    def get_boton_atras(self):
        return self.selenium.find_element(by=By.CLASS_NAME, value='atras')

    def insert_data(self, **kwargs):
        num_aut_box = self.selenium.find_element(by=By.NAME, value=kwargs.get('value'))
        num_aut_box.send_keys(kwargs.get('data'))
        return num_aut_box

    def animacion_works(self, animacion, id_btn='btn_conti'):
        self.selenium.execute_script(f'document.getElementById("{id_btn}").click(); window.stop()')
        works = animacion.value_of_css_property('display') == 'block'
        self.selenium.execute_script('window.location.reload()')
        return works

    def process_home(self):
        self.get_boton_continuar().click()

    def process_instrucciones(self):
        self.get_boton_continuar().click()
        if self.selenium.title != 'Autorización de servicio':
            self.take_me_to_the_step('autorizacionServicio')

    def process_autorizacion(self):
        num_aut_box = self.insert_data(value="autorizacionServicio-num_autorizacion", data='99999999')
        num_aut_box.send_keys(Keys.ENTER)
        if self.selenium.title != 'Foto de la fórmula':
            self.take_me_to_the_step('fotoFormulaMedica')

    def process_foto(self):
        img = BASE_DIR / 'core/apps/base/tests/resources/image_1.jpg'
        self.selenium.find_element(by=By.ID, value='id_fotoFormulaMedica-src').send_keys(str(img))
        self.get_boton_continuar().click()
        if self.selenium.title != 'Dirección':
            self.take_me_to_the_step('avisoDireccion')

    def process_aviso_direccion(self):
        mun, _ = Municipio.objects.get_or_create(name='barranquilla', departamento='atlántico')
        Barrio.objects.get_or_create(name='el recreo', municipio=mun, zona='norte',
                                     cod_zona=109, status=1)
        Barrio.objects.get_or_create(name='cevillar', municipio=mun, zona='sur',
                                     cod_zona=109, status=1)
        Barrio.objects.get_or_create(name='adelita de char', municipio=mun, zona='norte',
                                     cod_zona=109, status=1)
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
        self.selenium.find_element(by=By.ID, value='id_digitaDireccionBarrio-barrio_0').click()
        self.get_boton_continuar().click()
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

    def take_me_to_the_step(self, to_step):
        map_vistas = [
            {'Inicio': 'self.process_home()'},
            {'Instrucciones': 'self.process_instrucciones()'},
            {'Autorización de servicio': 'self.process_autorizacion()'},
            {'Foto de la fórmula': 'self.process_foto()'},
            {'Dirección': 'self.process_aviso_direccion()'},
            {'Elige Municipio': 'self.process_elige_municipio()'},
            {'Elige el barrio': 'self.process_direccion_barrio()'},
            {'Digite celular': 'self.process_celular()'},
            {'Digite un correo electrónico': 'self.process_correo()'},
        ]
        current = [i for i, v in enumerate(map_vistas) if list(v.keys()) == [self.selenium.title]]
        desde = current[0]
        hasta = self.vistas.index(to_step)
        # print(f"Al querer avanzar a {to_step}, fue llevado a {self.selenium.title}")
        if hasta - desde == 1:
            eval(list(map_vistas[desde].values())[0])
        else:
            # print(f'Voy a ir de {self.vistas[desde]} a {to_step}')
            for vista in map_vistas[desde:hasta]:
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

    def done(self, form_list, **kwargs):
        return render(self.request)


vistas = [Home, Instrucciones, AutorizacionServicio, FotoFormulaMedica,
          AvisoDireccion, EligeMunicipio, DireccionBarrio, DigitaCelular,
          DigitaCorreo]


class TestWizardWithInitAttrs(TestWizard):
    form_list = vistas
