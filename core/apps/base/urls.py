from django.urls import path

from core.apps.base.views import ContactWizard, finalizado

app_name = 'base'

urlpatterns = [
    path('', ContactWizard.as_view(), name='home'),
    path('finalizado/', finalizado, name='done')
]
