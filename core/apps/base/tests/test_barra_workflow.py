"""Tests for prescription OCR Barra (MCP lookup + SAP match) workflow."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from core.apps.base.models import (
    PrescriptionOCRBarraMapping,
    PrescriptionOCRBarraTransaction,
    PrescriptionOCRTransaction,
    SAPArticle,
    Status,
)
from core.apps.base.resources.ai.providers.base import BarraMcpLookupResult, LLMUsageMeta
from core.apps.base.resources.prescription_ocr.barra_service import (
    ensure_barra_jobs,
    poll_barra_job,
)


def _sap_defaults(**kwargs: object) -> dict:
    base: dict = {
        'external_id': 888001,
        'barra': '7701234567890',
        'descripcion': 'Producto prueba',
        'grupo_articulo': 'G',
        'molecula_id': 'M',
        'nombre_molecula': 'Mol',
        'cantidad_unidad_compra': Decimal('1'),
        'cantidad_unidad_venta': Decimal('1'),
        'fecha_creacion': date(2024, 1, 1),
        'usuario': 'u',
    }
    base.update(kwargs)
    return base


class BarraServiceTests(TestCase):
    databases = '__all__'

    def test_ensure_barra_jobs_skips_empty_articulos(self) -> None:
        ocr = PrescriptionOCRTransaction.objects.create(
            drive_file_id='f1',
            status=Status.COMPLETED.value,
            provider='anthropic',
            model_id='x',
            result={'IPS': 'IPS1', 'Articulos': []},
        )
        ensure_barra_jobs(ocr)
        self.assertEqual(ocr.barra_transactions.count(), 0)

    def test_ensure_barra_jobs_creates_pending(self) -> None:
        ocr = PrescriptionOCRTransaction.objects.create(
            drive_file_id='f2',
            status=Status.COMPLETED.value,
            provider='anthropic',
            model_id='x',
            result={
                'IPS': 'Clinica',
                'Articulos': [
                    {
                        'Numero': 1,
                        'Nombre': 'Esomeprazol 40 mg',
                    },
                ],
            },
        )
        ensure_barra_jobs(ocr)
        self.assertEqual(ocr.barra_transactions.count(), 1)
        job = ocr.barra_transactions.get()
        self.assertEqual(job.status, Status.PENDIENTE.value)
        self.assertEqual(job.article_nombre, 'Esomeprazol 40 mg')

    def test_poll_completes_with_fake_provider_and_sap(self) -> None:
        SAPArticle.objects.create(**_sap_defaults(barra='7701234567890', external_id=888002))
        ocr = PrescriptionOCRTransaction.objects.create(
            drive_file_id='f3',
            status=Status.COMPLETED.value,
            provider='anthropic',
            model_id='x',
            result={
                'IPS': 'Clinica',
                'Articulos': [{'Numero': 1, 'Nombre': 'Esomeprazol 40 mg'}],
            },
        )
        ensure_barra_jobs(ocr)
        job = ocr.barra_transactions.get()

        class _FakeBarra:
            def run_barra_mcp_lookup(self, request):
                return BarraMcpLookupResult(
                    text='7701234567890',
                    usage=LLMUsageMeta(
                        input_tokens=10,
                        output_tokens=5,
                        cache_read_input_tokens=None,
                        cost_usd='0.001000',
                        raw_usage={'input_tokens': 10, 'output_tokens': 5},
                    ),
                )

        data = poll_barra_job(job.pk, provider_factory=_FakeBarra)
        self.assertEqual(data['status'], Status.COMPLETED.value)
        assert data['sap_article'] is not None
        self.assertEqual(data['sap_article']['barra'], '7701234567890')
        self.assertTrue(
            PrescriptionOCRBarraMapping.objects.filter(
                ips='Clinica',
                nombre_articulo='Esomeprazol 40 mg',
            ).exists()
        )

    def test_poll_uses_mapping_cache_without_llm(self) -> None:
        SAPArticle.objects.create(**_sap_defaults(barra='9998887777666', external_id=888003))
        PrescriptionOCRBarraMapping.objects.create(
            ips='Clinica',
            nombre_articulo='Cached Drug',
            barra_llm='9998887777666',
            sap_barra='9998887777666',
            sap_external_id=888003,
            sap_descripcion='Cached Drug Desc',
        )
        ocr = PrescriptionOCRTransaction.objects.create(
            drive_file_id='f4',
            status=Status.COMPLETED.value,
            provider='anthropic',
            model_id='x',
            result={
                'IPS': 'Clinica',
                'Articulos': [{'Numero': 1, 'Nombre': 'Cached Drug'}],
            },
        )
        ensure_barra_jobs(ocr)
        job = ocr.barra_transactions.get()
        self.assertEqual(job.status, Status.COMPLETED.value)

        class _ShouldNotCall:
            def run_barra_mcp_lookup(self, request):
                raise AssertionError('LLM should not run when mapping cache hits')

        data = poll_barra_job(job.pk, provider_factory=_ShouldNotCall)
        self.assertEqual(data['status'], Status.COMPLETED.value)


class BarraAPITests(TestCase):
    databases = '__all__'

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username='barra_tester', password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_barra_poll_404(self) -> None:
        url = reverse('prescription_ocr_barra_poll', kwargs={'job_id': 999999})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_barra_poll_returns_snapshot(self) -> None:
        ocr = PrescriptionOCRTransaction.objects.create(
            drive_file_id='f5',
            status=Status.COMPLETED.value,
            provider='anthropic',
            model_id='x',
            result={
                'IPS': 'X',
                'Articulos': [{'Numero': 1, 'Nombre': 'Drug X'}],
            },
        )
        ensure_barra_jobs(ocr)
        job = PrescriptionOCRBarraTransaction.objects.get(
            prescription_ocr_transaction=ocr
        )
        job.status = Status.COMPLETED.value
        job.result = {
            'barra_llm': '123',
            'sap_article': {'barra': '123', 'descripcion': 'Y'},
        }
        job.save(update_fields=['status', 'result', 'updated_at'])
        url = reverse('prescription_ocr_barra_poll', kwargs={'job_id': job.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['job_id'], job.pk)
        self.assertIn('barra_aggregates', body)
