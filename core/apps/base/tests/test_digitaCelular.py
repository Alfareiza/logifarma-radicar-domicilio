from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from core import settings
from core.apps.base.forms import DigitaCelular
from core.apps.base.models import Barrio
from core.apps.base.tests.test_fotoFormulaMedica import upload_foto
from core.apps.base.tests.utilities import get_request, TestWizard
from core.apps.base.views import FORMS


class DigitaCelularWizardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        barrios = Barrio.objects.all()
        if barrios:
            cls.barrio_id = str(barrios[0].id)
            cls.municipio_id = str(barrios[0].municipio.id)

    def setUp(self):
        self.testform = TestWizard.as_view(FORMS)
        self.request = get_request({'test_wizard-current_step': 'home'})
        self.response, self.instance = self.testform(self.request)
        self.request.POST = {'test_wizard-current_step': 'autorizacionServicio',
                             'autorizacionServicio-num_autorizacion': 99_999_999}
        self.response, self.instance = self.testform(self.request)
        image = upload_foto()
        self.request.POST = {'test_wizard-current_step': 'fotoFormulaMedica'}
        self.request.FILES = MultiValueDict({'fotoFormulaMedica-src': [image['src']]})
        self.response, self.instance = self.testform(self.request)
        self.request.POST = {'test_wizard-current_step': 'eligeMunicipio',
                             'eligeMunicipio-municipio': DigitaCelularWizardTests.municipio_id}
        self.response, self.instance = self.testform(self.request)
        self.request.POST = {'test_wizard-current_step': 'digitaDireccionBarrio',
                             'digitaDireccionBarrio-direccion': 'AV MURILLO, 123456',
                             'digitaDireccionBarrio-barrio': DigitaCelularWizardTests.barrio_id}
        self.response, self.instance = self.testform(self.request)

    @classmethod
    def tearDownClass(cls):
        for file in settings.MEDIA_ROOT.iterdir():
            file.unlink()

    def test_step_name_is_digitaCelular(self):
        self.assertEqual(self.instance.steps.current, 'digitaCelular')

    def test_template_name_is_digita_celular_html(self):
        self.assertEqual(self.instance.get_template_names()[0], 'digita_celular.html')

    def test_nextstep_is_digitaCorreo(self):
        self.assertEqual(self.instance.get_next_step(), 'digitaCorreo')

    def test_going_to_next_step(self):
        self.request.POST = {'test_wizard-current_step': 'digitaCelular',
                             'digitaCelular-celular': 321_456_9874}
        response, instance = self.testform(self.request)

        #  Al ser realizado el POST, deberá entrar en la siguiente vista
        self.assertEqual(self.instance.steps.current, 'digitaCorreo', 'No se pudo avanzar al siguiente paso')
        self.assertIn('digitaCelular', instance.storage.data['step_data'])


class DigitaCelularFormTests(TestCase):
    def test_invalid_numbers(self):
        for number in [-123456, 1, 310_123_456, 414_123_4567]:
            with self.subTest(i=number):
                form = DigitaCelular(data={'celular': number})
                self.assertFalse(form.is_valid())
                self.assertIn(f"Número de celular incorrecto:\n{number}", form.errors.as_text())

    def test_valid_number(self):
        for number in [300_000_0000, 301_601_2996, 311_111_1111]:
            with self.subTest(i=number):
                form = DigitaCelular(data={'celular': number})
                self.assertTrue(form.is_valid())
