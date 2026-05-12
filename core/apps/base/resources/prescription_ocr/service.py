"""Orchestrate prescription OCR: cache, lock, Drive download, LLM, persistence."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from core.apps.base.exceptions import OcrLockBusy
from core.apps.base.models import PrescriptionOCRTransaction, Radicacion, Status
from core.apps.base.resources.ai.providers.anthropic import AnthropicStructuredVisionProvider
from core.apps.base.resources.ai.providers.base import (
    AnthropicProvider,
    PrescriptionOCRResult,
    VisionStructuredRequest,
    VisionStructuredResult,
)
from core.apps.base.resources.prescription_ocr.goals.prescription_extraction import (
    PRESCRIPTION_EXTRACTION_GOAL,
    PRESCRIPTION_EXTRACTION_MODEL_ID_DEFAULT,
    StructuredVisionGoal
)
from core.apps.base.resources.prescription_ocr.locking import prescription_ocr_file_lock
from core.apps.tasks.utils.gdrive import GDriveHandler
from core.settings import logger

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PrescriptionOCRRunOutcome:
    """Result of a single OCR run attempt (including cache hits and recoverable failures)."""

    transaction: PrescriptionOCRTransaction
    cached: bool
    error: Literal['drive', 'llm'] | None = None
    reason: str = None


@dataclass(frozen=True, slots=True)
class PrescriptionOCRDiscardOutcome:
    """Discard endpoint result prior to HTTP mapping."""

    ok: bool
    reason: Literal['not_found', 'mismatch'] | None = None


def _completed_cache_query(file_id: str):
    return (
        PrescriptionOCRTransaction.objects.filter(
            drive_file_id=file_id,
            status=Status.COMPLETED.value,
            discard=False,
        )
        .exclude(result__isnull=True)
        .order_by('-created_at')
    )


class PrescriptionOCRService:
    """
    Application service for OCR over a Drive file id.

    In tests, inject alternate ``drive`` or ``llm_factory`` doubles.
    """

    def __init__(
        self,
        *,
        drive: Any | None = None,
        llm_factory: Callable[[], AnthropicProvider]
        | None = None,
        model_id: str | None = None,
        goal: StructuredVisionGoal | None = None,
    ) -> None:
        self._drive = drive if drive is not None else GDriveHandler()
        self._llm_factory = llm_factory or AnthropicStructuredVisionProvider
        self._goal = goal if goal is not None else PRESCRIPTION_EXTRACTION_GOAL
        self._model_id = model_id or PRESCRIPTION_EXTRACTION_MODEL_ID_DEFAULT

    def run_from_drive(
        self,
        *,
        drive_file_id: str,
        image_url_normalized: str,
        radicacion: Radicacion | None,
    ) -> PrescriptionOCRRunOutcome:
        """
        Cache lookup → lock → create RUNNING txn → Drive → Anthropic → COMPLETED.

        Raises:
            OcrLockBusy: Another caller holds the per-file OCR lock for this Drive id.

        Notes:
            On Drive or LLM failure the transaction row is persisted as ``FAILED``.
        """
        if hit := _completed_cache_query(drive_file_id).first():
            return PrescriptionOCRRunOutcome(transaction=hit, cached=True, error=None)

        with prescription_ocr_file_lock(drive_file_id):
            hit_in = _completed_cache_query(drive_file_id).first()
            if hit_in:
                return PrescriptionOCRRunOutcome(transaction=hit_in, cached=True, error=None)

            txn = PrescriptionOCRTransaction.objects.create(
                drive_file_id=drive_file_id,
                radicacion=radicacion,
                image_url=(image_url_normalized or '')[:2048],
                status=Status.RUNNING.value,
                provider='anthropic',
                model_id=self._model_id,
                discard=False,
            )

            try:
                raw_bytes, mime = self._drive.download_file_bytes(drive_file_id)
            except Exception:
                log.exception(
                    f'GDrive download failed file_id={drive_file_id}'
                )
                txn.status = Status.FAILED.value
                txn.error_message = 'drive_download_failed'
                txn.save(update_fields=['status', 'error_message', 'updated_at'])
                return PrescriptionOCRRunOutcome(
                    transaction=txn,
                    cached=False,
                    error='drive',
                )

            try:
                provider: AnthropicStructuredVisionProvider = self._llm_factory()
                req: VisionStructuredRequest = self._goal.build_request(
                    raw_bytes,
                    mime,
                    model_id=self._model_id,
                )
                out: VisionStructuredResult = provider.run_vision_json_schema(req)
                prescription_ocr_result: PrescriptionOCRResult = out.prescription_ocr_result
                usage = out.usage
                meta_tokens = usage.input_tokens
                meta_out_tokens = usage.output_tokens
                meta_cache_read = usage.cache_read_input_tokens
                cost_raw = usage.cost_usd
                meta_raw_usage = usage.raw_usage
            except Exception as exc:
                log.exception(f'Anthropic OCR failed file_id={drive_file_id}')
                txn.status = Status.FAILED.value
                txn.error_message = str(exc)[:4000]
                txn.save(update_fields=['status', 'error_message', 'updated_at'])
                return PrescriptionOCRRunOutcome(
                    transaction=txn,
                    cached=False,
                    error='llm',
                    reason=txn.error_message
                )

            txn.result = prescription_ocr_result.model_dump()
            if (txn.result['TipoDocumentoPaciente'] and txn.result['TipoDocumentoPaciente'] != radicacion.tipo_documento_paciente) or (txn.result['NumeroDocumentoPaciente'] and txn.result['NumeroDocumentoPaciente'] != radicacion.numero_documento_paciente):
                logger.error(f"Documento escaneado no coincide con documento de radicación", 
                extra={"numero_autorizacion": radicacion.numero_autorizacion, "convenio": radicacion.convenio, "OCR Result": f"Tipo Documento {txn.result['TipoDocumentoPaciente']!r}, Documento {txn.result['NumeroDocumentoPaciente']}",
                "Radicación":f"Tipo Documento {radicacion.tipo_documento_paciente!r}, Documento {radicacion.numero_documento_paciente}"}
                )
            
            txn.status = Status.COMPLETED.value
            txn.model_id = self._model_id
            txn.input_tokens = meta_tokens
            txn.output_tokens = meta_out_tokens
            txn.cache_read_input_tokens = meta_cache_read
            if cost_raw:
                txn.cost_usd = Decimal(cost_raw)
            txn.raw_usage = meta_raw_usage
            txn.save()
            return PrescriptionOCRRunOutcome(
                transaction=txn,
                cached=False,
                error=None,
            )

    def discard_transaction(
        self,
        *,
        transaction_id: int,
        drive_file_id_normalized: str | None,
    ) -> PrescriptionOCRDiscardOutcome:
        """
        Mark a transaction as discarded (excluding it from OCR cache lookups).

        If ``drive_file_id_normalized`` is set, require an exact match to the stored id.
        """
        txn = PrescriptionOCRTransaction.objects.filter(pk=transaction_id).first()
        if not txn:
            return PrescriptionOCRDiscardOutcome(ok=False, reason='not_found')
        expected = drive_file_id_normalized
        if expected and txn.drive_file_id != expected:
            return PrescriptionOCRDiscardOutcome(ok=False, reason='mismatch')

        if not txn.discard:
            txn.discard = True
            txn.save(update_fields=['discard', 'updated_at'])

        return PrescriptionOCRDiscardOutcome(ok=True, reason=None)
