from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from core import settings
from core.apps.base.forms import AvisoDireccion
from core.apps.base.models import Municipio, Barrio
from core.apps.base.tests.test_fotoFormulaMedica import upload_foto
from core.apps.base.tests.utilities import get_request, TestWizard
from core.apps.base.views import FORMS


class AvisoDireccionWizardTests(TestCase):
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

    @classmethod
    def tearDownClass(cls):
        for file in settings.MEDIA_ROOT.iterdir():
            file.unlink()

    def test_step_name_is_avisoDireccion(self):
        self.assertEqual(self.instance.steps.current, 'avisoDireccion')

    def test_template_name_is_foto_html(self):
        self.assertEqual(self.instance.get_template_names()[0], 'aviso_direccion.html')

    def test_nextstep_is_eligeMunicipio(self):
        self.assertEqual(self.instance.get_next_step(), 'eligeMunicipio')

    def test_going_to_next_step(self):
        self.request.POST = {'test_wizard-current_step': 'avisoDireccion'}
        response, instance = self.testform(self.request)

        #  Al ser realizado el POST, deberá entrar en la siguiente vista
        self.assertEqual(instance.steps.current, 'eligeMunicipio')
        self.assertIn('avisoDireccion', instance.storage.data['step_data'])


class AvisoDireccionFormTests(TestCase):
    def test_basic_form(self):
        form = AvisoDireccion(data={})
        self.assertTrue(form.is_valid())
