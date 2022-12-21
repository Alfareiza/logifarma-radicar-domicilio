from django.test import TransactionTestCase
from django.utils.datastructures import MultiValueDict

from core import settings
from core.apps.base.models import Municipio, Barrio
from core.apps.base.tests.test_fotoFormulaMedica import upload_foto
from core.apps.base.tests.test_wizards import TestWizard, get_request
from core.apps.base.views import FORMS


class DigitaDireccionBarrioWizardTests(TransactionTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mun = Municipio.objects.create(name='barranquilla', departamento='atlantico')
        cls.barr = Barrio.objects.create(name='el recreo', municipio=cls.mun,
                                         zona='norte', cod_zona=109,
                                         status=1)

    def setUp(self):
        self.testform = TestWizard.as_view(FORMS)
        self.request = get_request({'test_wizard-current_step': 'home'})
        self.response, self.instance = self.testform(self.request)
        self.request.POST = {'test_wizard-current_step': 'instrucciones'}
        self.response, self.instance = self.testform(self.request)
        self.request.POST = {'test_wizard-current_step': 'autorizacionServicio',
                             'autorizacionServicio-num_autorizacion': 99_999_999}
        self.response, self.instance = self.testform(self.request)
        image = upload_foto()
        self.request.POST = {'test_wizard-current_step': 'fotoFormulaMedica'}
        self.request.FILES = MultiValueDict({'fotoFormulaMedica-src': [image['src']]})
        self.response, self.instance = self.testform(self.request)
        self.request.POST = {'test_wizard-current_step': 'avisoDireccion'}
        self.response, self.instance = self.testform(self.request)
        self.request.POST = {'test_wizard-current_step': 'eligeMunicipio',
                             'eligeMunicipio-municipio': '1'}
        self.response, self.instance = self.testform(self.request)

    @classmethod
    def tearDownClass(cls):
        for file in settings.MEDIA_ROOT.iterdir():
            file.unlink()

    def test_step_name_is_eligeMunicipio(self):
        self.assertEqual(self.instance.steps.current, 'digitaDireccionBarrio')

    def test_template_name_is_direccion_barrio_html(self):
        self.assertEqual(self.instance.get_template_names()[0], 'direccion_barrio.html')

    def test_nextstep_is_digitaCelular(self):
        self.assertEqual(self.instance.get_next_step(), 'digitaCelular')

    def test_going_to_next_step(self):
        self.request.POST = {'test_wizard-current_step': 'digitaDireccionBarrio',
                             'digitaDireccionBarrio-direccion': 'AV MURILLO, 123456',
                             'digitaDireccionBarrio-barrio': str(DigitaDireccionBarrioWizardTests.barr.id)}
        response, instance = self.testform(self.request)

        #  Al ser realizado el POST, deberá entrar en la siguiente vista
        self.assertEqual(self.instance.steps.current, 'digitaCelular', 'No se pudo avanzar al siguiente paso')
        self.assertIn('digitaDireccionBarrio', instance.storage.data['step_data'])
