from django.urls import path

from core.apps.base.forms import *
from core.apps.base.views import ContactWizard, finalizado, err_multitabs
from core.apps.base.views_sin_autorizacion import SinAutorizacion

app_name = 'base'

urlpatterns = [
    path('', ContactWizard.as_view(), name='home'),
    path('sin-autorizacion/', SinAutorizacion.as_view(), name='sin-autorizacion'),
    path('finalizado/', finalizado, name='done'),
    path('error/', err_multitabs, name='err_multitabs')
]
