from __future__ import annotations


class UserNotFound(Exception):
    ...


class NroAutorizacionNoEncontrado(Exception):
    ...


class NoRecordsInTable(Exception):
    ...


class FieldError(Exception):
    ...


class NoImageWindow(Exception):
    ...


class PasoNoProcesado(Exception):
    ...


class RestartScrapper(Exception):
    ...

class SinAutorizacionesPorRadicar(Exception):
    ...

class TransactionRolledBack(Exception):
    """Exception lanzada cuando al haber establecido la fecha en el modal, se clica en 'Confirmar fecha prest', se encuentra el texto 'Transacion Rolled Back', en la respuesta."""
    ...

class OcrLockBusy(Exception):
    """
    Raised when another request holds the OCR lock for the same Drive file.

    Mapped to HTTP 409 in the prescription OCR API view.
    """


class DriveFileIdNormalizationError(ValueError):
    """
    Invalid Drive file id or URL.

    ``detail`` matches what DRF expects in ``serializers.ValidationError(detail=...)``
    (either a string message or a dict of field errors).
    """

    def __init__(self, detail: str | dict[str, str]):
        self.detail = detail
        super().__init__(str(detail))
