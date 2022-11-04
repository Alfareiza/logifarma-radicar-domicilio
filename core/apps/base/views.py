from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse
from formtools.wizard.views import SessionWizardView

from core.apps.base.forms import *


def home(request):
    '''Vista 1: Página inicial de la aplicación'''
    # return render(request, 'base/home.html')
    return render(request, "base/home.html", )


def instrucciones(request):
    '''Vista 2: Página que indica los pasos'''
    return render(request, "base/instrucciones.html", )


def autorizacion_servicio(request):
    '''
    Vista 3:
    Página que recibe autorización de servicio y
    la verifica en 2 APIs externas.
    Si la respuesta es positiva, hará un redirect
    a la vista 4, sino  responderá con un mensaje de 
    error.
    '''
    ...

def foto(request):
    '''
    Vista 4:
    '''
    return render(request, "base/foto.html", )


FORMS = [
    ("home", Home),
    ("instrucciones", Instrucciones),
    ("autorizacionServicio", AutorizacionServicio),
    ("fotoFormulaMedica", FotoFormulaMedica),
    ("avisoDireccion", AvisoDireccion),
    ("eligeMunicipio", EligeMunicipio),
    ("eligeBarrio", EligeBarrio),
    ("digitaDireccion", DigitaDireccion),
    ("digitaCelular", DigitaCelular)
]

TEMPLATES = {"home": "home.html",
             "instrucciones": "instrucciones.html",
             "autorizacionServicio": "autorizacion.html",
             "fotoFormulaMedica": "foto.html",
             "avisoDireccion": "aviso_direccion.html",
             "eligeMunicipio": "elige_municipio.html",
             "eligeBarrio": "elige_barrio.html",
             "digitaDireccion": "digita_direccion.html",
             "digitaCelular": "digita_celular.html"}


class ContactWizard(SessionWizardView):
    # template_name = 'start.html'
    form_list = FORMS

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]
    def done(self, form_list, **kwargs):
        return render(self.request, 'done.html', {
            'form_data': [form.cleaned_data for form in form_list],
        })
