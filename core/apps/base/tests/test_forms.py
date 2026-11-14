from django import forms
from django.test import TestCase

from core.apps.base.models import (
    Barrio,
    Municipio,
    Radicacion,
    UsuariosPermitidosPanales,
)
from core.apps.base.validators import validate_panales


class ValidatePanalesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.doc = '12340316'
        cls.num_aut = 5000102222999
        cls.resp_eps = {
            'DOCUMENTO_ID': cls.doc,
            'TIPO_IDENTIFICACION': 'CC',
            'P_NOMBRE': 'JUAN',
            'SEDE_AFILIADO': 'bogota',
            'DETALLE_AUTORIZACION': [{'NOMBRE_PRODUCTO': 'PANALES', 'CUMS': '1', 'CANTIDAD': 1}],
        }
        mun = Municipio.objects.create(name='villavicencio', departamento='meta')
        cls.barrio = Barrio.objects.create(
            name='brisas', municipio=mun, zona='norte', cod_zona=109, status=1,
        )

    def test_bloquea_primera_vez(self):
        with self.assertRaises(forms.ValidationError) as ctx:
            validate_panales(self.resp_eps, self.num_aut)
        self.assertEqual(ctx.exception.message, 'Pañales bloqueados.')

    def test_permite_si_hay_radicado_reciente(self):
        Radicacion.objects.create(
            numero_radicado=str(self.num_aut),
            municipio=self.barrio.municipio,
            barrio=self.barrio,
            email='a@b.com',
            direccion='calle 1',
            ip='127.0.0.1',
            paciente_nombre='JUAN',
            paciente_cc=self.doc,
            paciente_data={
                'DETALLE_AUTORIZACION': [{'NOMBRE_PRODUCTO': 'PANALES'}],
            },
        )
        validate_panales(self.resp_eps, self.num_aut)

    def test_permite_si_esta_en_allowlist(self):
        UsuariosPermitidosPanales.objects.create(
            tipo_documento='CC', documento=self.doc, motivo='Caso especial',
        )
        validate_panales(self.resp_eps, self.num_aut)

    def test_permite_allowlist_sin_tipo_en_resp(self):
        UsuariosPermitidosPanales.objects.create(
            tipo_documento='CC', documento=self.doc,
        )
        resp = {**self.resp_eps}
        resp.pop('TIPO_IDENTIFICACION')
        validate_panales(resp, self.num_aut)
