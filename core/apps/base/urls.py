"""URL mappings for the base app (transaction app)"""

from django.urls import path

from core.apps.base.views import ContactWizard, ve

app_name = 'base'

urlpatterns = [
    path('', ContactWizard.as_view(), name='home'),
    path('ve', ve, name='ve')
]
