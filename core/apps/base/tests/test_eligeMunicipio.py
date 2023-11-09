from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from core import settings
from core.apps.base.forms import EligeMunicipio
from core.apps.base.models import Barrio
from core.apps.base.tests.test_fotoFormulaMedica import upload_foto
from core.apps.base.tests.utilities import get_request, TestWizard
from core.apps.base.views import FORMS


class EligeMunicipioWizardTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        barrios = Barrio.objects.all()
        if barrios:
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

    @classmethod
    def tearDownClass(cls):
        for file in settings.MEDIA_ROOT.iterdir():
            file.unlink()

    def test_step_name_is_eligeMunicipio(self):
        self.assertEqual(self.instance.steps.current, 'eligeMunicipio')

    def test_template_name_is_elige_municipio_html(self):
        self.assertEqual(self.instance.get_template_names()[0], 'elige_municipio.html')

    def test_nextstep_is_eligeMunicipio(self):
        self.assertEqual(self.instance.get_next_step(), 'digitaDireccionBarrio')

    def test_going_to_next_step(self):
        self.request.POST = {'test_wizard-current_step': 'eligeMunicipio',
                             'eligeMunicipio-municipio': EligeMunicipioWizardTests.municipio_id}
        response, instance = self.testform(self.request)

        #  Al ser realizado el POST, deberá entrar en la siguiente vista
        self.assertEqual(self.instance.steps.current, 'digitaDireccionBarrio')
        self.assertIn('eligeMunicipio', instance.storage.data['step_data'])

    def test_choosing_municipio(self):
        # mun = Municipio.objects.get(name='barranquilla')
        form = EligeMunicipio(data={'municipio': str(EligeMunicipioWizardTests.municipio_id)})
        self.assertTrue(form.is_valid())
