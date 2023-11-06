from django.test import TestCase

from core.apps.base.forms import SinAutorizacion


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
