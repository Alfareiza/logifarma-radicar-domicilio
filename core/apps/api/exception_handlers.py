# core/apps/api/exception_handlers.py
from django.db.utils import OperationalError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, OperationalError):
        return Response(
            {'detail': 'Base de datos temporalmente no disponible. Intente nuevamente.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return None