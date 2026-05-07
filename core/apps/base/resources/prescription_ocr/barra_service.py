"""Per-article barcode resolution: enqueue jobs, mapping cache, poll-claim-run via MCP + SAP."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404

from core.apps.base.resources.tools import remove_accents
from core.settings import logger
from core.apps.base.models import (
    SearchBarra,
    PrescriptionOCRTransaction,
    SAPArticle,
    Status,
)
from core.apps.base.resources.ai.providers.anthropic import AnthropicBarraMcpProvider
from core.apps.base.resources.ai.providers.base import AnthropicProvider, BarraMcpLookupResult, BarraMcpLookupRequest
from core.apps.base.resources.prescription_ocr.goals.barra_lookup import BARRA_LOOKUP_GOAL

log = logging.getLogger(__name__)

# Allow typical SAP internal barcodes (alphanumeric + hyphen); strip whitespace first.
_BARRA_RE = re.compile(r'^[0-9]{1,50}$')


def normalize_mapping_key(ips: str, nombre: str) -> tuple[str, str]:
    ips_k = (ips or '').strip()[:512]
    nombre_k = ' '.join((nombre or '').split())[:512]
    return ips_k, nombre_k


def normalize_barra_candidate(raw: str) -> str:
    if not raw:
        return ''
    line = str(raw).strip().splitlines()[0].strip()
    line = re.sub(r'\s+', '', line)
    return line[:50]


def sap_article_to_dict(a: SAPArticle) -> dict[str, Any]:
    return {
        'external_id': a.external_id,
        'barra': a.barra,
        'descripcion': a.descripcion,
        'nombre_molecula': a.nombre_molecula,
        'forma_farmaceutica': a.forma_farmaceutica or '',
        'grupo_articulo': a.grupo_articulo,
        'molecula_id': a.molecula_id,
        'cum': a.cum or '',
        'invima': a.invima or '',
        'atc': a.atc or '',
        'fabricante': a.fabricante or '',
        'marca': a.marca or '',
        'regulado': a.regulado,
        'inactivo': a.inactivo,
        'ultima_compra': a.ultima_compra.isoformat() if a.ultima_compra else None,
    }


def barra_aggregates(ocr_txn: PrescriptionOCRTransaction) -> dict[str, Any]:
    qs = ocr_txn.barra_transactions.all()
    total = qs.count()
    pending = qs.filter(status=Status.PENDIENTE.value).count()
    running = qs.filter(status=Status.RUNNING.value).count()
    completed = qs.filter(status=Status.COMPLETED.value).count()
    failed = qs.filter(status=Status.FAILED.value).count()
    cost_sum = qs.aggregate(s=Sum('cost_usd'))['s'] or Decimal('0')
    return {
        'jobs_total': total,
        'jobs_pending': pending,
        'jobs_running': running,
        'jobs_completed': completed,
        'jobs_failed': failed,
        'cost_usd_total': str(cost_sum.quantize(Decimal('0.000001'))),
    }


def barra_jobs_for_api(ocr_txn: PrescriptionOCRTransaction) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for j in ocr_txn.barra_transactions.order_by('article_numero', 'id'):
        res = j.result if isinstance(j.result, dict) else {}
        row: dict[str, Any] = {
            'job_id': j.pk,
            'article_numero': j.article_numero,
            'article_nombre': j.article_nombre,
            'status': j.status,
        }
        if res.get('sap_article'):
            row['sap_article'] = res['sap_article']
        if res.get('barra_llm'):
            row['barra_llm'] = res['barra_llm']
        if j.error_message:
            row['error_message'] = j.error_message
        rows.append(row)
    return rows


def _execute_job_llm(
    job: SearchBarra,
    provider_factory: Callable[[], AnthropicBarraMcpProvider] | None = None,
) -> None:
    """Execute a barcode lookup job using AI with MCP. If the barcode is not found, the job is failed. Otherwise, the job is completed."""
    req: BarraMcpLookupRequest = BARRA_LOOKUP_GOAL.build_request(job.article_nombre)
    provider: AnthropicBarraMcpProvider = provider_factory()
    logger.info(f'Executing barra job {job.pk} with request for {job.article_nombre!r}')
    out: BarraMcpLookupResult = provider.run_barra_mcp_lookup(req)
    logger.info(f'Barra job {job.pk} finished with request for {job.article_nombre!r}')
    usage = out.usage
    job.model_id = req.model_id
    job.input_tokens = usage.input_tokens
    job.output_tokens = usage.output_tokens
    job.cache_read_input_tokens = usage.cache_read_input_tokens
    if usage.cost_usd:
        job.cost_usd = Decimal(usage.cost_usd)
    job.raw_usage = usage.raw_usage

    if not out.text or not _BARRA_RE.match(out.text):
        job.status = Status.FAILED.value
        job.error_message = 'invalid_barra_response'
        job.result = {'barra_llm': out.text, 'raw_llm_text': (out.text or '')[:2000], 'raw_response': str(out.raw_response), 'input_raw': str(out.input_raw)}
        job.save()
        return

    sap = SAPArticle.objects.filter(barra=out.text).first()
    if not sap:
        job.status = Status.FAILED.value
        job.error_message = f'No encontrado el código de barras {out.text!r} en base de datos'
        job.result = {'barra_llm': out.text, 'raw_llm_text': (out.text or '')[:500]}
        job.save()
        return
    else:
        job.result = out.text
        job.article_sap = sap
        job.status = Status.COMPLETED.value
        job.save()
        return

def ensure_barra_jobs(ocr_txn: PrescriptionOCRTransaction) -> None:
    """Create process to find out barcodes in sap_articles table for each article in the prescription OCR."""
    data = ocr_txn.result or {}
    arts = data.get('Articulos') or []
    if not arts:
        return
    
    ips = str(data.get('IPS') or '')
    used_nums: set[int] = set()

    for idx, raw in enumerate(arts):
        nombre = (raw.get('Nombre') or '').strip()
        if not nombre:
            continue
        n_raw = raw.get('Numero')
        try:
            num = (
                int(n_raw)
                if n_raw is not None and str(n_raw).strip() != ''
                else idx + 1
            )
        except (TypeError, ValueError):
            num = idx + 1
        while num in used_nums:
            num += 1
        used_nums.add(num)

        qs = SearchBarra.objects.filter(ips=ips, article_nombre=nombre, status=Status.COMPLETED.value)
        if qs.exists():
            job = qs.first()
            job.pk = None
            job.prescription_ocr_transaction=ocr_txn
            job.article_numero=num
            job.raw_usage = None
            job.input_tokens = 0
            job.output_tokens = 0
            job.cache_read_input_tokens = 0
            job.cost_usd = Decimal('0')
            job.save()
        else:
            job = SearchBarra.objects.create(
                prescription_ocr_transaction=ocr_txn,
                article_numero=num,
                article_nombre=nombre[:512].upper().strip(),
                ips=remove_accents(ips[:512]).upper().strip(),
                status=Status.PENDIENTE.value,
                provider='anthropic',
                model_id=BARRA_LOOKUP_GOAL.model_id,
            )


def poll_barra_job(
    job: SearchBarra,
    *,
    provider_factory: Callable[[], AnthropicProvider] | None = None,
) -> SearchBarra:
    """
    Poll one job: if ``pendiente``, claim (``en ejecucion``) and run MCP + SAP match.
    Returns the refreshed job instance; serialization is the caller's responsibility.
    """
    provider_factory = provider_factory or AnthropicBarraMcpProvider
    # Nothing to do — job is already terminal or owned by another worker.
    if job.status in (Status.COMPLETED.value, Status.FAILED.value, Status.RUNNING.value):
        return job

    # Attempt to claim the PENDIENTE job atomically.
    claimed = False
    with transaction.atomic():
        locked = (
            SearchBarra.objects
            .select_for_update(skip_locked=True)
            .filter(pk=job.pk, status=Status.PENDIENTE.value)
            .first()
        )
        if locked:
            locked.status = Status.RUNNING.value
            locked.save(update_fields=['status', 'updated_at'])
            claimed = True

    job.refresh_from_db()

    if not claimed:
        return job

    try:
        _execute_job_llm(job, provider_factory)
    except Exception as exc:
        log.exception(f'Barra MCP job failed job_id={job.pk}', )
        job.refresh_from_db()
        if job.status not in (Status.COMPLETED.value, Status.FAILED.value):
            job.status = Status.FAILED.value
            job.error_message = str(exc)[:4000]
            job.save(update_fields=['status', 'error_message', 'updated_at'])

    job.refresh_from_db()
    return job
