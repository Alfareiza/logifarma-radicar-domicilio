import random
import unittest

from django.test import TestCase

from core.apps.base.forms import AutorizacionServicio
from core.apps.base.models import Radicacion, Municipio, Barrio
from core.apps.base.tests.utilities import get_request, TestWizard
from core.apps.base.views import FORMS


class AutorizacionWizardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        mun = Municipio.objects.create(name='villavicencio', departamento='meta')
        barr = Barrio.objects.create(name='brisas del caney y sausalito', municipio=mun,
                                     zona='norte', cod_zona=109,
                                     status=1)
        rad = Radicacion.objects.create(numero_radicado=str(5000102222349),
                                        municipio=mun, barrio=barr,
                                        cel_uno=str(3211234567), cel_dos=None,
                                        email='janedoe@gmail.com',
                                        direccion='Cualquier direccion', ip='192.168.0.1',
                                        paciente_nombre='GUTIERREZ TEIXEIRA JACKSON HOW',
                                        paciente_cc='12340316', paciente_data={})

    def setUp(self) -> None:
        self.testform = TestWizard.as_view(FORMS)
        self.request = get_request({'test_wizard-current_step': 'home'})
        self.response, self.instance = self.testform(self.request)

    def test_step_name_is_autorizacionServicio(self):
        self.assertEqual(self.instance.steps.current, 'autorizacionServicio')

    def test_template_name_is_autorizacion_html(self):
        self.assertEqual(self.instance.get_template_names()[0], 'autorizacion.html')

    def test_nextstep_is_fotoFormulaMedica(self):
        self.assertEqual(self.instance.get_next_step(), 'fotoFormulaMedica')

    def test_99_999_999_is_ok(self):
        """Comprueba que el valor ingresado pasó las validaciones y acceso a la sgte vista"""
        self.request.POST = {'test_wizard-current_step': 'autorizacionServicio',
                             'autorizacionServicio-num_autorizacion': 99_999_999}
        response, instance = self.testform(self.request)
        self.assertEqual(self.instance.steps.current, 'fotoFormulaMedica')
        self.assertIn('autorizacionServicio', instance.storage.data['step_data'])

    def test_sending_empty_value(self):
        self.request.POST = {'test_wizard-current_step': 'autorizacionServicio',
                             'autorizacionServicio-num_autorizacion': ''}
        response, instance = self.testform(self.request)
        self.assertNotIn('autorizacionServicio', instance.storage.data['step_data'])
        self.assertIn(
            """<div class="modal" id="modal_vist">
                <div class="conten" id="cont_mod">
                    <header></header>
                    <div class="modal_btn">
                        <button type="button" id="btn_modal" class="close">X</button>
                    </div>""", response.rendered_content)
        self.assertIn('Este campo es obligatorio.', response.rendered_content)

    def test_less_than_100_000(self):
        number = random.randint(1, 100_000 - 1)
        self.request.POST = {'test_wizard-current_step': 'autorizacionServicio',
                             'autorizacionServicio-num_autorizacion': number}
        response, instance = self.testform(self.request)
        self.assertIn(
            """<div class="modal" id="modal_vist">
                <div class="conten" id="cont_mod">
                    <header></header>
                    <div class="modal_btn">
                        <button type="button" id="btn_modal" class="close">X</button>
                    </div>""", response.rendered_content)
        self.assertIn("Asegúrese de que este valor sea mayor o igual a 100000.", response.rendered_content)

    def test_radicacion_existent(self):
        rad = Radicacion.objects.get(numero_radicado=str(5000102222349))
        self.request.POST = {'test_wizard-current_step': 'autorizacionServicio',
                             'autorizacionServicio-num_autorizacion': rad.numero_radicado}
        response, instance = self.testform(self.request)
        self.assertIn(
            """<div class="modal" id="modal_vist">
                <div class="conten" id="cont_mod">
                    <header></header>
                    <div class="modal_btn">
                        <button type="button" id="btn_modal" class="close">X</button>
                    </div>""", response.rendered_content)
        self.assertIn("Numero de autorización 5000102222349 se encuentra radicado", response.rendered_content)


class AutorizacionFormTests(TestCase):

    def test_invalid_numbers(self):
        for number in [-123456, 1, 0]:
            with self.subTest(i=number):
                form = AutorizacionServicio(data={'num_autorizacion': number})
                self.assertFalse(form.is_valid())
                self.assertEqual(form.errors['num_autorizacion'],
                                 ['Asegúrese de que este valor sea mayor o igual a 100000.'])

    def test_number_99_999_999_return_json(self):
        form = AutorizacionServicio(data={'num_autorizacion': 99_999_999})
        self.assertTrue(form.is_valid())
        self.assertDictEqual(form.cleaned_data, {'num_autorizacion': {'TIPO_IDENTIFICACION': 'CC',
                                                                      'DOCUMENTO_ID': '12340316',
                                                                      'AFILIADO': 'GUTIERREZ TEIXEIRA JACKSON WOH',
                                                                      'ESTADO_AFILIADO': 'ACTIVO',
                                                                      'SEDE_AFILIADO': 'BARRANCABERMEJA',
                                                                      'REGIMEN': 'SUBSIDIADO',
                                                                      'DIRECCION': 'CL 123  45 678',
                                                                      'CORREO': 'jackson.gutierrez.teixeira123456789@gmail.com',
                                                                      'TELEFONO': '4019255',
                                                                      'CELULAR': '4014652512',
                                                                      'ESTADO_AUTORIZACION': 'PROCESADA',
                                                                      'FECHA_AUTORIZACION': '15/11/2022',
                                                                      'MEDICO_TRATANTE': 'FRANK LAMPARD',
                                                                      'MIPRES': '0',
                                                                      'DIAGNOSTICO': 'D571-ANEMIA FALCIFORME SIN CRISIS',
                                                                      'DETALLE_AUTORIZACION': [{'CUMS': '20158642-1',
                                                                                                'NOMBRE_PRODUCTO': 'RIVAROXABAN 20MG TABLETA RECUBIERTA',
                                                                                                'CANTIDAD': '30'},
                                                                                               {'CUMS': '42034-1',
                                                                                                'NOMBRE_PRODUCTO': 'HIDROXIUREA 500MG CAPSULA',
                                                                                                'CANTIDAD': '60'}],
                                                                      'municipio': 'Barrancamerbeja, Santander',
                                                                      'barrio': 'Any Neighbor, Florida',
                                                                      'direccion': '321654987654',
                                                                      'celular': 9151234567,
                                                                      'email': '23131@gmail.com',
                                                                      'NUMERO_AUTORIZACION': 99999999}})

    @unittest.skip("Only works if is executed from a Colombian public network")
    def test_number_not_found_in_db(self):
        form = AutorizacionServicio(data={'num_autorizacion': 123_456_789})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['num_autorizacion'], [
            'Número de autorización 123456789 no encontrado\n\nPor favor verifique\n\nSi el número está correcto, comuníquese con cajacopi EPS\nal 01 8000 111 446'])

    @unittest.skip("Only works if is executed from a Colombian public network")
    def test_valid_number(self):
        form = AutorizacionServicio(data={'num_autorizacion': 5_000_102_226_929})
        self.assertTrue(form.is_valid())
        self.assertEqual(list(form.cleaned_data.keys()), ['num_autorizacion'])
        self.assertEqual(
            sorted(list(form.cleaned_data['num_autorizacion'])),
            ['AFILIADO',
             'CELULAR',
             'CORREO',
             'DETALLE_AUTORIZACION',
             'DIAGNOSTICO',
             'DIRECCION',
             'DOCUMENTO_ID',
             'ESTADO_AFILIADO',
             'ESTADO_AUTORIZACION',
             'FECHA_AUTORIZACION',
             'MEDICO_TRATANTE',
             'MIPRES',
             'NUMERO_AUTORIZACION',
             'REGIMEN',
             'SEDE_AFILIADO',
             'TELEFONO',
             'TIPO_IDENTIFICACION']
        )
