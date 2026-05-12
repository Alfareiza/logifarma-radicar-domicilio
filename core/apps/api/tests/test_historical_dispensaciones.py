"""Tests for GET /api/v1/historical-dispensations/<documento>/ and Pydantic parsing."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.apps.base.resources.medicar import HistoricoDispensados

SAMPLE_HISTORICO = [
    {
        'TipoDoc': 'CC',
        'NumeroDocumento': '22479430',
        'Afiliado': 'PACIENTE TEST',
        'PendientesActivos': True,
        'SSCs': [
            {
                'SSC': 9915040,
                'SubPlan': 'Capita complementaria Subsidiado',
                'Autorizacion': '',
                'MIPRES': '',
                'FecSol': '2026-05-08 07:48:43',
                'Centro': '920',
                'NombCaf': 'Central Domicilios Barranquilla (920)',
                'Articulos': [
                    {
                        'CodMol': 22501,
                        'Plu': '7707334710348',
                        'Descripcion': 'FOSFOMICINA 3 MG POLVO ORAL',
                        'CantidadSolicitada': 24,
                        'CantidadPendiente': 24,
                        'InventarioMoleculaCentro': 7,
                        'TotalPendienteMoleculaCentro': 35,
                        'TransitoMoleculaCentro': 30,
                        'Dispensaciones': [
                            {
                                'CantidadDispensada': 5,
                                'FecDisp': '2026-05-08 07:48:43',
                            },
                            {
                                'CantidadDispensada': 3,
                                'FecDisp': '2026-05-09 08:00:00',
                            },
                        ],
                    }
                ],
            }
        ],
    }
]


class HistoricoDispensadosPydanticTests(SimpleTestCase):
    """No database required."""

    def test_sum_cantidad_dispensada_por_cod_mol(self) -> None:
        h = HistoricoDispensados.model_validate(SAMPLE_HISTORICO)
        self.assertEqual(h.sum_cantidad_dispensada_por_cod_mol(22501), 8)
        self.assertEqual(h.sum_cantidad_dispensada_por_cod_mol(99999), 0)


class HistoricalDispensacionesApiTests(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user('historico_tester', password='historico-pass')
        self.url = reverse('historical_dispensaciones', kwargs={'documento': '22479430'})

    def test_requires_auth(self) -> None:
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    @patch('core.apps.api.views.obtener_historico_dispensados_usuario')
    def test_returns_json_list_when_authenticated(self, mock_med: object) -> None:
        mock_med.return_value = SAMPLE_HISTORICO
        self.client.force_login(self.user)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['NumeroDocumento'], '22479430')
        mock_med.assert_called_once_with('22479430')

    @patch('core.apps.api.views.obtener_historico_dispensados_usuario')
    def test_non_list_response_is_502(self, mock_med: object) -> None:
        mock_med.return_value = {'error': 'unexpected'}
        self.client.force_login(self.user)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn('detail', res.data)
