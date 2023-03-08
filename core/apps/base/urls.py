from django.urls import path

from core.apps.base.views_api import AuthViewSet
from core.apps.base.views import ContactWizard, finalizado

app_name = 'base'

urlpatterns = [
    path('', ContactWizard.as_view(), name='home'),
    path('finalizado/', finalizado, name='done')
]

from rest_framework import routers

router = routers.DefaultRouter(trailing_slash=False)
router.register('api/auth', AuthViewSet, basename='auth')

urlpatterns += router.urls
