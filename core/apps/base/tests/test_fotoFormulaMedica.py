import mimetypes

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from core import settings
from core.apps.base.forms import FotoFormulaMedica
from core.apps.base.tests.test_wizards import TestWizard, get_request
from core.apps.base.views import FORMS
from core.settings import BASE_DIR


def upload_foto(filepath=None):
    if filepath is None:
        filepath = BASE_DIR / 'core/apps/base/tests/resources/image_1.jpg'
    return {
        'src': SimpleUploadedFile(
            filepath.name,
            content=open(filepath, 'rb').read(),
            content_type=mimetypes.MimeTypes().guess_type(filepath)[0])
    }


class FotoWizardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.testform = TestWizard.as_view(FORMS)
        cls.request = get_request({'test_wizard-current_step': 'home'})
        cls.response, cls.instance = cls.testform(cls.request)
        cls.request.POST = {'test_wizard-current_step': 'instrucciones'}
        cls.response, cls.instance = cls.testform(cls.request)
        cls.request.POST = {'test_wizard-current_step': 'autorizacionServicio',
                             'autorizacionServicio-num_autorizacion': 99_999_999}
        cls.response, cls.instance = cls.testform(cls.request)

    @classmethod
    def tearDownClass(cls):
        for file in settings.MEDIA_ROOT.iterdir():
            file.unlink()

    def test_step_name_is_fotoFormulaMedica(self):
        self.assertEqual(self.instance.steps.current, 'fotoFormulaMedica')

    def test_template_name_is_foto_html(self):
        self.assertEqual(self.instance.get_template_names()[0], 'foto.html')

    def test_nextstep_is_avisoDireccion(self):
        self.assertEqual(self.instance.get_next_step(), 'avisoDireccion')

    def test_uploading_image_is_ok(self):
        image = upload_foto()
        self.request.POST = {'test_wizard-current_step': 'fotoFormulaMedica'}
        self.request.FILES = MultiValueDict({'fotoFormulaMedica-src': [image['src']]})
        response, instance = self.testform(self.request)

        # Al ser realizado el POST con la foto, deberá entrar en la siguiente vista
        self.assertEqual(instance.steps.current, 'avisoDireccion')
        self.assertIn('fotoFormulaMedica', instance.storage.data['step_data'])


class FotoFormTests(TestCase):
    def test_loading_photo_jpg(self):
        form = FotoFormulaMedica({}, upload_foto())
        self.assertTrue(form.is_valid())
