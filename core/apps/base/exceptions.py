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
