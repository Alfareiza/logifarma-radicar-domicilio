from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from .views import RadicacionViewSet

router = DefaultRouter()
router.register(r"radicaciones", RadicacionViewSet, basename="radicaciones")

urlpatterns = [
    path('schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='api-schema'),
         name='api-docs'),
    path("", include(router.urls)),
]
