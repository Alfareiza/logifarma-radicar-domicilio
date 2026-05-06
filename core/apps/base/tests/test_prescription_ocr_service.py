"""Tests for prescription OCR orchestration and discard validation."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from core.apps.api.serializers import PrescriptionOCRDiscardSerializer
from core.apps.base.models import PrescriptionOCRTransaction, Status
from core.apps.base.resources.ai.providers.base import (
    LLMUsageMeta,
    PrescriptionOCRResult,
    VisionStructuredResult,
)
from core.apps.base.resources.prescription_ocr.goals.prescription_extraction import (
    PRESCRIPTION_EXTRACTION_MODEL_ID_DEFAULT,
)
from core.apps.base.resources.prescription_ocr.service import PrescriptionOCRService

_DRIVE_ID = 'fileid123450'

_MIN_SCHEMA_RESULT = {
    'IPS': '',
    'FechaFormula': '',
    'TipoDocumentoPaciente': '',
    'NumeroDocumentoPaciente': '',
    'NombrePaciente': '',
    'NombreMedico': '',
    'DiagnosticoPrincipal': {'Codigo': '', 'Descripcion': ''},
    'OtrosDiagnosticos': [],
    'Articulos': [],
}


class _FakeDriveGood:
    def download_file_bytes(self, file_id: str) -> tuple[bytes, str]:
        return b'\xff\xd8\xff\xdb', 'image/jpeg'


class _FakeDriveBroken:
    def download_file_bytes(self, file_id: str) -> tuple[bytes, str]:
        raise OSError('network')


class _FakeLLMGood:
    def run_vision_json_schema(self, request):
        ocr_result = PrescriptionOCRResult(
            IPS='',
            FechaFormula='',
            TipoDocumentoPaciente='',
            NumeroDocumentoPaciente='',
            NombrePaciente='',
            NombreMedico='',
            DiagnosticoPrincipal=None,
            OtrosDiagnosticos=None,
            Articulos=[],
        )
        return VisionStructuredResult(
            prescription_ocr_result=ocr_result,
            usage=LLMUsageMeta(
                input_tokens=100,
                output_tokens=50,
                cache_read_input_tokens=None,
                cost_usd='0.010000',
                raw_usage={
                    'input_tokens': 100,
                    'output_tokens': 50,
                },
            ),
        )


class _FakeLLMBroken:
    def run_vision_json_schema(self, request):
        raise ValueError('model exploded')


def _noop_lock():
    """Context manager that does nothing (bypass real DB advisory lock)."""

    class _CM:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    return _CM()


class PrescriptionOCRServiceTests(TestCase):
    databases = '__all__'

    def test_cache_hit_short_circuits_before_drive(self):
        existing = PrescriptionOCRTransaction.objects.create(
            drive_file_id=_DRIVE_ID,
            status=Status.COMPLETED.value,
            provider='anthropic',
            model_id=PRESCRIPTION_EXTRACTION_MODEL_ID_DEFAULT,
            discard=False,
            result=_MIN_SCHEMA_RESULT,
            image_url='',
        )

        bad_drive = _FakeDriveBroken()

        with patch(
            'core.apps.base.resources.prescription_ocr.service.prescription_ocr_file_lock',
            return_value=_noop_lock(),
        ):
            svc = PrescriptionOCRService(drive=bad_drive, llm_factory=_FakeLLMGood)
            out = svc.run_from_drive(
                drive_file_id=_DRIVE_ID,
                image_url_normalized='https://example.com/',
                radicacion=None,
            )

        self.assertTrue(out.cached)
        self.assertIsNone(out.error)
        self.assertEqual(out.transaction.pk, existing.pk)

    def test_drive_failure_sets_status_failed(self):
        with patch(
            'core.apps.base.resources.prescription_ocr.service.prescription_ocr_file_lock',
            return_value=_noop_lock(),
        ):
            svc = PrescriptionOCRService(
                drive=_FakeDriveBroken(), llm_factory=_FakeLLMGood
            )
            out = svc.run_from_drive(
                drive_file_id=_DRIVE_ID,
                image_url_normalized='',
                radicacion=None,
            )

        self.assertEqual(out.error, 'drive')
        txn = PrescriptionOCRTransaction.objects.latest('pk')
        self.assertEqual(txn.status, Status.FAILED.value)
        self.assertEqual(txn.error_message, 'drive_download_failed')

    def test_llm_failure_sets_status_failed(self):
        with patch(
            'core.apps.base.resources.prescription_ocr.service.prescription_ocr_file_lock',
            return_value=_noop_lock(),
        ):
            svc = PrescriptionOCRService(
                drive=_FakeDriveGood(),
                llm_factory=_FakeLLMBroken,
            )
            out = svc.run_from_drive(
                drive_file_id=_DRIVE_ID,
                image_url_normalized='',
                radicacion=None,
            )

        self.assertEqual(out.error, 'llm')
        txn = PrescriptionOCRTransaction.objects.latest('pk')
        self.assertEqual(txn.status, Status.FAILED.value)

    def test_success_persists_result(self):
        with patch(
            'core.apps.base.resources.prescription_ocr.service.prescription_ocr_file_lock',
            return_value=_noop_lock(),
        ):
            svc = PrescriptionOCRService(
                drive=_FakeDriveGood(),
                llm_factory=_FakeLLMGood,
            )
            out = svc.run_from_drive(
                drive_file_id=_DRIVE_ID,
                image_url_normalized='',
                radicacion=None,
            )

        self.assertIsNone(out.error)
        self.assertFalse(out.cached)
        txn = out.transaction
        self.assertEqual(txn.status, Status.COMPLETED.value)
        self.assertEqual(txn.result, _MIN_SCHEMA_RESULT)
        self.assertEqual(txn.input_tokens, 100)


class PrescriptionOCRDiscardSerializerTests(TestCase):
    def test_discard_normalizes_optional_drive_id(self):
        ser = PrescriptionOCRDiscardSerializer(
            data={
                'transaction_id': 1,
                'drive_file_id': '  fileid123450  ',
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(
            ser.validated_data['drive_file_id_normalized_optional'], 'fileid123450'
        )


class PrescriptionOCRDiscardAPITests(TestCase):
    databases = '__all__'

    def setUp(self):
        self.user = User.objects.create_user(
            username='ocr_tester', password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_discard_accepts_whitespace_stripped_canonical_id(self):
        txn = PrescriptionOCRTransaction.objects.create(
            drive_file_id=_DRIVE_ID,
            status=Status.COMPLETED.value,
            provider='anthropic',
            model_id=PRESCRIPTION_EXTRACTION_MODEL_ID_DEFAULT,
            discard=False,
            result=_MIN_SCHEMA_RESULT,
            image_url='',
        )
        url = reverse('prescription_ocr_discard')
        resp = self.client.post(
            url,
            {
                'transaction_id': txn.pk,
                'drive_file_id': f'  {_DRIVE_ID}  ',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        txn.refresh_from_db()
        self.assertTrue(txn.discard)

    def test_discard_rejects_other_canonical_id(self):
        txn = PrescriptionOCRTransaction.objects.create(
            drive_file_id=_DRIVE_ID,
            status=Status.COMPLETED.value,
            provider='anthropic',
            model_id=PRESCRIPTION_EXTRACTION_MODEL_ID_DEFAULT,
            discard=False,
            result=_MIN_SCHEMA_RESULT,
            image_url='',
        )
        other_id = 'otherid12345'
        url = reverse('prescription_ocr_discard')
        resp = self.client.post(
            url,
            {'transaction_id': txn.pk, 'drive_file_id': other_id},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        txn.refresh_from_db()
        self.assertFalse(txn.discard)
