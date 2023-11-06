import unittest

from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from core import settings
from core.apps.base.forms import DigitaCelular, DigitaCorreo
from core.apps.base.models import Municipio, Barrio
from core.apps.base.tests.test_fotoFormulaMedica import upload_foto
from core.apps.base.tests.utilities import get_request, TestWizard
from core.apps.base.views import FORMS


class DigitaCorreoWizardTests(TestCase):
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
        self.request.POST = {'test_wizard-current_step': 'autorizacionServicio',
                             'autorizacionServicio-num_autorizacion': 99_999_999}
        self.response, self.instance = self.testform(self.request)
        image = upload_foto()
        self.request.POST = {'test_wizard-current_step': 'fotoFormulaMedica'}
        self.request.FILES = MultiValueDict({'fotoFormulaMedica-src': [image['src']]})
        self.response, self.instance = self.testform(self.request)
        self.request.POST = {'test_wizard-current_step': 'eligeMunicipio',
                             'eligeMunicipio-municipio': '1'}
        self.response, self.instance = self.testform(self.request)
        self.request.POST = {'test_wizard-current_step': 'digitaDireccionBarrio',
                             'digitaDireccionBarrio-direccion': 'AV MURILLO, 123456',
                             'digitaDireccionBarrio-barrio': str(DigitaCorreoWizardTests.barr.id)}
        self.response, self.instance = self.testform(self.request)
        self.request.POST = {'test_wizard-current_step': 'digitaCelular',
                             'digitaCelular-celular': 321_456_9874}
        self.response, self.instance = self.testform(self.request)
        self.instance.storage.current_step = 'digitaCorreo'

    @classmethod
    def tearDownClass(cls):
        for file in settings.MEDIA_ROOT.iterdir():
            file.unlink()

    # def test_step_name_is_digitaCorreo(self):
    #     self.assertEqual(self.instance.steps.current, 'digitaCorreo')
    #
    # def test_template_name_is_digita_correo_html(self):
    #     self.assertEqual(self.instance.get_template_names()[0], 'digita_correo.html')
    #
    # def test_nextstep_is_done(self):
    #     self.assertEqual(self.instance.get_next_step(), None)

    # def test_going_to_next_step_empty_email(self):
    #     self.request.POST = {'test_wizard-current_step': 'digitaCorreo',
    #                          'digitaCorreo-email': 'jane@doe.com'}
    #     import pdb; breakpoint()
    #     response, instance = self.testform(self.request)
    #
    #     #  Al ser realizado el POST, deberá entrar en la siguiente vista
    #     self.assertEqual(self.instance.steps.current, 'digitaCorreo', 'No se pudo avanzar al siguiente paso')
    #     self.assertIn('digitaCorreo', instance.storage.data['step_data'])


class DigitaCorreoFormTests(TestCase):
    # @unittest.skip("Is not working until a regex for validation email is implemented")
    def test_invalid_emails(self):
        for email in (-123456, 'google.com', 'google@.com', '123', 'a@a', '@456.com', 'calderón cadlo@gmail.com',
                      'añoñi@hotmail.com'):
            with self.subTest(i=email):
                form = DigitaCorreo(data={'email': email})
                self.assertFalse(form.is_valid())
                self.assertEqual(form.errors.get_json_data()['__all__'][0]['message'],
                                 'E-mail inválido.')

    def test_valid_emails(self):
        for email in ('a@a.com', 'jane@doe.com', 'a@456.com', 'foobar@gmaul.com', '1@a.com, 2@b.com'):
            with self.subTest(i=email):
                form = DigitaCorreo(data={'email': email})
                self.assertTrue(form.is_valid())
