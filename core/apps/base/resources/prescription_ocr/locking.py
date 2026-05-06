"""
Mutual exclusion for cold OCR runs on a single Google Drive file id.

Prevents overlapping Anthropic + Drive downloads for the same image. PostgreSQL uses
session advisory locks; other databases use Django cache (single-process caveat).
"""

from __future__ import annotations

import zlib
from contextlib import contextmanager

from django.core.cache import cache
from django.db import connection

from core.apps.base.exceptions import OcrLockBusy


def _lock_int(drive_file_id: str) -> int:
    """Derive a non-negative integer key for PostgreSQL advisory locks."""
    return zlib.crc32(drive_file_id.encode('utf-8')) & 0x7FFFFFFF


LOCK_CACHE_PREFIX = 'prescription_ocr_lock:'


@contextmanager
def prescription_ocr_file_lock(drive_file_id: str, timeout: int = 600):
    """
    Hold an exclusive lock for the duration of a cold OCR run for ``drive_file_id``.

    Postgres: ``pg_try_advisory_lock`` / ``pg_advisory_unlock`` at session scope.
    Other vendors: atomic ``cache.add`` with TTL fallback (fine for SQLite dev).

    Args:
        drive_file_id: Google Drive file id string.
        timeout: Seconds to retain cache-based lock before auto-expiry (non-Postgres).

    Raises:
        OcrLockBusy: If the lock could not be acquired immediately.
    """
    key_int = _lock_int(drive_file_id)
    acquired = False
    if connection.vendor == 'postgresql':
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_try_advisory_lock(%s)', [key_int])
                acquired = bool(cursor.fetchone()[0])
            if not acquired:
                raise OcrLockBusy(drive_file_id)
            yield
        finally:
            if acquired:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_unlock(%s)', [key_int])
        return

    cache_key = f'{LOCK_CACHE_PREFIX}{drive_file_id}'
    if not cache.add(cache_key, 1, timeout=timeout):
        raise OcrLockBusy(drive_file_id)
    try:
        yield
    finally:
        cache.delete(cache_key)
