from django.urls import path

from core.apps.base.views import ContactWizard, finalizado, err_multitabs, WizardConMutualSerScrapping
from core.apps.base.views_sin_autorizacion import SinAutorizacion
from core.apps.base.views_mutualser import MutualSerAutorizacion

app_name = 'base'

urlpatterns = [
    path('', ContactWizard.as_view(), name='home'),
    # path('prueba/', WizardConMutualSerScrapping.as_view(), name='home_prueba'),
    path('sin-autorizacion/', SinAutorizacion.as_view(), name='sin-autorizacion'),
    path('mutualser/', MutualSerAutorizacion.as_view(), name='mutualser'),
    path('finalizado/', finalizado, name='done'),
    path('error/', err_multitabs, name='err_multitabs')
]
