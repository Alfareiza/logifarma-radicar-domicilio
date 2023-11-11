from django.urls import path

from core.apps.base.forms import *
from core.apps.base.views import ContactWizard, finalizado, err_multitabs
from core.apps.base.views_sin_autorizacion import SinAutorizacion

app_name = 'base'

FORMS = [
    ("home", Home),
    ("autorizado_o_no", AutorizadoONo),
    ("autorizacionServicio", AutorizacionServicio),
    ("fotoFormulaMedica", FotoFormulaMedica),
    ("eligeMunicipio", EligeMunicipio),
    ("digitaDireccionBarrio", DireccionBarrio),
    ("digitaCelular", DigitaCelular),
    ("digitaCorreo", DigitaCorreo)
]

urlpatterns = [
    path('', ContactWizard.as_view(), name='home'),
    path('g/', ContactWizard.as_view(FORMS), name='f'),
    path('sin-autorizacion/', SinAutorizacion.as_view(), name='sin-autorizacion'),
    path('finalizado/', finalizado, name='done'),
    path('error/', err_multitabs, name='err_multitabs')
]
