import django;
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

django.setup()

from core import settings
from core.apps.base.forms import SinAutorizacion
from core.apps.base.models import Barrio
from core.apps.base.tests.test_fotoFormulaMedica import upload_foto
from core.apps.base.tests.utilities import get_request, TestWizard, TestWizardSinAutorizacion
from core.apps.base.views_sin_autorizacion import FORMS


class SinAutorizacionWizardTests(TestCase):
    """This tests guarantee that its possible to go through the steps
    and post the data into the 'digita correo' step."""

    @classmethod
    def setUpTestData(cls):
        barrios = Barrio.objects.all()
        if barrios:
            cls.barrio_id = str(barrios[0].id)
            cls.municipio_id = str(barrios[0].municipio.id)

    def setUp(self):
        self.testform = TestWizardSinAutorizacion.as_view(FORMS)
        self.request = get_request({'test_wizard_sin_autorizacion-current_step': 'sinAutorizacion'})
        self.response, self.instance = self.testform(self.request)
        self.request.POST = MultiValueDict({'test_wizard_sin_autorizacion-current_step': ['sinAutorizacion'],
                                            'sinAutorizacion-tipo_identificacion': ['CC'],
                                            'sinAutorizacion-identificacion': ['99999999']})
        self.response, self.instance = self.testform(self.request)
        image = upload_foto()
        self.request.POST = MultiValueDict({'test_wizard_sin_autorizacion-current_step': ['fotoFormulaMedica']})
        self.request.FILES = MultiValueDict({'fotoFormulaMedica-src': [image['src']]})
        self.response, self.instance = self.testform(self.request)
        self.request.POST = MultiValueDict({'test_wizard_sin_autorizacion-current_step': ['eligeMunicipio'],
                                            'eligeMunicipio-municipio': [SinAutorizacionWizardTests.municipio_id]})
        self.response, self.instance = self.testform(self.request)
        self.request.POST = MultiValueDict({'test_wizard_sin_autorizacion-current_step': ['digitaDireccionBarrio'],
                                            'digitaDireccionBarrio-direccion': ['AV MURILLO, 123456'],
                                            'digitaDireccionBarrio-barrio': [SinAutorizacionWizardTests.barrio_id]})
        self.response, self.instance = self.testform(self.request)
        self.request.POST = MultiValueDict({'test_wizard_sin_autorizacion-current_step': ['digitaCelular'],
                                            'digitaCelular-celular': [321_456_9874]})
        self.response, self.instance = self.testform(self.request)
        self.request.POST = MultiValueDict({'test_wizard_sin_autorizacion-current_step': ['digitaCorreo'],
                                            'digitaCelular-celular': ['']})
        self.response, self.instance = self.testform(self.request)
        # self.instance.storage.current_step = 'digitaCorreo'

    @classmethod
    def tearDownClass(cls):
        for file in settings.MEDIA_ROOT.iterdir():
            file.unlink()

    def test_going_to_next_step(self):
        self.assertTrue(self.response.url == '/finalizado/')
        self.assertEqual(self.response.status_code, 302)

    def test_resolve_redirect(self):
        response = self.client.get(self.response.url, follow=True)
        self.assertEqual(response.request['PATH_INFO'], '/')


class SinAutorizacionFormTests(TestCase):
    def test_formulario_ok(self):
        form = SinAutorizacion(data={'tipo_identificacion': 'CC', 'identificacion': '99999999'})

        self.assertTrue(form.is_valid())
        resp = form.cleaned_data
        self.assertEqual(resp, {'documento': 'CC99999999',
                                'AFILIADO': 'DA SILVA RODRIQUEZ MARCELO SOUZA',
                                'NOMBRE': 'MARCELO DA SILVA',
                                'P_NOMBRE': 'MARCELO',
                                'TIPO_IDENTIFICACION': 'CC',
                                'DOCUMENTO_ID': '99999999'}
                         )
