from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from .views import RadicacionViewSet, busca_paciente, sms_create, sms_verify

router = DefaultRouter()
router.register(r"radicaciones", RadicacionViewSet, basename="radicaciones")

urlpatterns = [
    path('schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='api-schema'),
         name='api-docs'),
    path("busca-paciente/", busca_paciente, name="busca-paciente"),
    path("sms/create", sms_create, name="sms_create"),
    path("sms/verify", sms_verify, name="sms_verify"),
    path("", include(router.urls)),
]
