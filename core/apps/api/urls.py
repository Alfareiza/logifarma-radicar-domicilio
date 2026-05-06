from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from .views import (
    RadicacionViewSet,
    busca_paciente,
    prescription_ocr_barra_poll,
    prescription_ocr_discard,
    prescription_ocr_run,
    sms_create,
    sms_verify,
)

router = DefaultRouter()
router.register(r"radicaciones", RadicacionViewSet, basename="radicaciones")

urlpatterns = [
    path('schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='api-schema'),
         name='api-docs'),
    path("prescription-ocr/", prescription_ocr_run, name="prescription_ocr_run"),
    path(
        "prescription-ocr/barra/<int:job_id>/",
        prescription_ocr_barra_poll,
        name="prescription_ocr_barra_poll",
    ),
    path("prescription-ocr/discard/", prescription_ocr_discard,
         name="prescription_ocr_discard"),
    path("busca-paciente/", busca_paciente, name="busca-paciente"),
    path("sms/create", sms_create, name="sms_create"),
    path("sms/verify", sms_verify, name="sms_verify"),
    path("", include(router.urls)),
]
