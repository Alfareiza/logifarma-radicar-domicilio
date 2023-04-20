import datetime
import unittest
from unittest import TestCase

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.apps.api.serializers import RadicacionDetailSerializer, \
    RadicacionSerializer
from core.apps.api.views import create_range_dates
from core.apps.base.models import Barrio, Municipio, Radicacion

RADICACIONES_URL = reverse('radicaciones-list')


def detail_url(numero_radicacion):
    return reverse('radicaciones-detail', args=[numero_radicacion])


def create_municipio(**kwargs):
    """Create a municipio. Must receive a municipio object"""
    defaults = {
        'name': 'leticia',
        'departamento': 'amazonas'
    }
    defaults.update(kwargs)
    return Municipio.objects.create(**defaults)


def create_barrio(**kwargs):
    """Create a barrio. Must receive at least a municipio object"""
    defaults = {
        'name': 'barrio 1',
        'zona': 'zona norte',
        'cod_zona': 100,
        'status': 1,
    }
    defaults.update(kwargs)
    return Barrio.objects.create(**defaults)


def create_radicacion(**kwargs):
    defaults = {
        'paciente_nombre': 'foo bar',
        'numero_radicado': '5000102290907',
        'cel_uno': '3214567890',
        'email': 'jane@doe.com',
        'direccion': 'CL 45 # 34 - 122',
        'paciente_cc': '968574123',
        'ip': '192.168.0.1',
        'paciente_data': ''
    }
    defaults.update(kwargs)
    return Radicacion.objects.create(**defaults)


class RadicacionApiTests(TestCase):

    def setUp(self) -> None:
        self.client = APIClient()
        self.mun = create_municipio()
        self.barr = create_barrio(municipio=self.mun)
        self.rad = create_radicacion(numero_radicado='123456123456',
                                     barrio=self.barr,
                                     municipio=self.mun)

    def tearDown(self) -> None:
        Municipio.objects.filter(name=f'{self.mun.name}').first().delete()

    def test_get_list_radicacion(self):
        """Testing GET /api/v1/radicaciones/"""
        create_radicacion(numero_radicado='987654567891', barrio=self.barr,
                          municipio=self.mun)
        res = self.client.get(RADICACIONES_URL)

        enddate, startdate = create_range_dates()
        radicaciones = Radicacion.objects.filter(
            datetime__range=[startdate, enddate]
        ).order_by('-datetime')
        serializer = RadicacionSerializer(radicaciones, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['results'], serializer.data)

    def test_get_radicacion_detail(self):
        """Testing GET /api/v1/radicaciones/123456789"""
        url = detail_url(self.rad)
        res = self.client.get(url)

        serializer = RadicacionDetailSerializer(self.rad)
        self.assertEqual(res.data, serializer.data)

    @unittest.skip("Only works if is executed with production db")
    def test_get_radicacion_detail_specific_one(self):
        """Testing GET /api/v1/radicaciones/800102253316"""
        input_rad = 800102253316
        url = detail_url(input_rad)
        res = self.client.get(url)
        rad = Radicacion.objects.get(numero_radicado=input_rad)

        serializer = RadicacionDetailSerializer(rad)
        self.assertEqual(res.data, serializer.data)


    def test_create_radicacion(self):
        """Testing POST /api/v1/radicaciones/"""
        payload = {
            'paciente_nombre': 'jane doe',  # Obligatório
            'numero_radicado': '921122119',  # Obligatório
            'cel_uno': '3226546541',  # Opcional
            'cel_dos': '3106560000',  # Opcional
            'email': 'jane.doe@email.com',  # Obligatório
            'direccion': 'KR 4 # 3 - 22',  # Obligatório
            'paciente_cc': '65498745',  # Obligatório
            'municipio_id': 1,  # Obligatório
            'barrio_id': 1,  # Obligatório
        }
        res = self.client.post(RADICACIONES_URL, data=payload, format='json')

        radicacion = Radicacion.objects.filter(
            numero_radicado=res.data['numero_radicado']
        ).first()

        serializer = RadicacionDetailSerializer(radicacion)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data, serializer.data)

        radicacion.delete()

    def test_partial_update_radicacion(self):
        """Testing PATCH /api/v1/radicaciones/123456123456"""
        payload = {
            'acta_entrega': '3450439',
        }
        url = detail_url(self.rad)
        res = self.client.patch(url, data=payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.rad.refresh_from_db()
        self.assertEqual(self.rad.acta_entrega, payload['acta_entrega'])

        # The object wasn't reached
        self.assertEqual(self.rad.direccion, 'CL 45 # 34 - 122')

    def test_partial_update_radicacion_not_allowed_field(self):
        """
        Testing PATCH /api/v1/radicaciones/123456123456
        sending a field that is not allowed to change.
        Obs.: The list of fields that not allow to change is on
              RadicacionPartialUpdateSerializer.
        """
        payload = {
            'cel_uno': '3101244',
        }
        url = detail_url(self.rad)
        res = self.client.patch(url, data=payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.rad.refresh_from_db()
        self.assertEqual(res.data, {'Invalid fields': 'cel_uno'})

        # The object wasn't reached
        self.assertEqual(self.rad.direccion, 'CL 45 # 34 - 122')

    def test_partial_update_radicacion_not_allowed_and_allowed_fields(self):
        """
        Testing PATCH /api/v1/radicaciones/123456123456
        Sending fields that are not allowed to change and other who are.
        Obs.: The list of fields that not allow to change is on
              RadicacionPartialUpdateSerializer.
        """
        payload = {
            "paciente_cc": "0",
            "acta_entrega": "410487",
        }
        url = detail_url(self.rad)
        res = self.client.patch(url, data=payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.rad.refresh_from_db()
        self.assertEqual(res.data, {'Invalid fields': 'paciente_cc'})

        # The object wasn't reached
        self.assertEqual(self.rad.paciente_cc, '968574123')
        self.assertEqual(self.rad.acta_entrega, None)

    def test_partial_update_radicacion_datetimefields_valid_format(self):
        """
        Testing PATCH /api/v1/radicaciones/123456123456
        Sending fields which in the model are DateTimeField.
        """
        payload = {"alistamiento": "2023-04-17 17:15"}
        url = detail_url(self.rad)
        res = self.client.patch(url, data=payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.rad.refresh_from_db()
        self.assertEqual(res.data['alistamiento'], "2023-04-17 17:15")

        # In the bd it is a datetime object
        self.assertIsInstance(self.rad.alistamiento, datetime.datetime)

        # The object wasn't reached
        self.assertEqual(self.rad.paciente_cc, '968574123')

    def test_partial_update_radicacion_datetimefields_invalid_format(self):
        """
        Testing PATCH /api/v1/radicaciones/123456123456
        Sending fields which in the model are DateTimeField.
        """
        payload = {"alistamiento": "0"}
        url = detail_url(self.rad)
        res = self.client.patch(url, data=payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.rad.refresh_from_db()
        self.assertEqual(res.data, {
            'Invalid format date': "time data '0' does not match format '%Y-%m-%d %H:%M'"})

        # The object wasn't reached
        self.assertEqual(self.rad.alistamiento, None)
