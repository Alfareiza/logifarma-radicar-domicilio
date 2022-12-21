from collections import OrderedDict
from importlib import import_module

from django import http
from django.conf import settings
from django.core.files.storage import DefaultStorage
from django.shortcuts import render
from django.test import TestCase
from django.urls import reverse
from formtools.wizard.views import (
    WizardView,
)

from core.apps.base.forms import *
from core.apps.base.views import FORMS, TEMPLATES, ContactWizard


class DummyRequest(http.HttpRequest):
    def __init__(self, POST=None):
        super().__init__()
        self.method = "POST" if POST else "GET"
        if POST is not None:
            self.POST.update(POST)
        self.session = {}
        self._dont_enforce_csrf_checks = True


def get_request(*args, **kwargs):
    request = DummyRequest(*args, **kwargs)
    engine = import_module(settings.SESSION_ENGINE)
    request.session = engine.SessionStore(None)
    return request


class TestWizard(WizardView):
    storage_name = 'formtools.wizard.storage.session.SessionStorage'
    file_storage = DefaultStorage()

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        return response, self

    def get_form_kwargs(self, step, *args, **kwargs):
        kwargs = super().get_form_kwargs(step, *args, **kwargs)
        if step == 'kwargs_test':
            kwargs['test'] = True
        return kwargs

    def get_form(self, step=None, data=None, files=None):
        form = super(TestWizard, self).get_form(step, data, files)
        step = step or self.steps.current
        if step == 'digitaDireccionBarrio':
            if form1_cleaned_data := self.get_cleaned_data_for_step('eligeMunicipio'):
                barrios_mun = Barrio.objects.filter(
                    municipio__id=form1_cleaned_data['municipio'].id
                ).order_by('name')
                form.fields['barrio'].choices = [(str(b.id), b.name.title()) for b in barrios_mun]
                form.fields['barrio'].choices.insert(0, ('X', 'Seleccione el barrio'))
        return form


    def done(self, form_list, **kwargs):
        # form_data = self.process_from_data(form_list)
        return render(self.request,
                      'done.html',
                      # context={'form_data': form_data}
                      )


vistas = [Home, Instrucciones, AutorizacionServicio, FotoFormulaMedica,
          AvisoDireccion, EligeMunicipio, DireccionBarrio, DigitaCelular,
          DigitaCorreo]


class TestWizardWithInitAttrs(TestWizard):
    form_list = vistas


class FormTests(TestCase):
    def test_status_code_200(self):
        response = self.client.get(reverse('base:home'))
        self.assertEqual(response.status_code, 200)

    def test_form_init(self):
        testform = TestWizard.get_initkwargs(FORMS)
        self.assertEqual(testform['form_list'], {"home": Home,
                                                 "instrucciones": Instrucciones,
                                                 "autorizacionServicio": AutorizacionServicio,
                                                 "fotoFormulaMedica": FotoFormulaMedica,
                                                 "avisoDireccion": AvisoDireccion,
                                                 "eligeMunicipio": EligeMunicipio,
                                                 "digitaDireccionBarrio": DireccionBarrio,
                                                 "digitaCelular": DigitaCelular,
                                                 "digitaCorreo": DigitaCorreo})

        testform = TestWizardWithInitAttrs.get_initkwargs()
        self.assertEqual(testform['form_list'], {'0': Home, '1': Instrucciones,
                                                 '2': AutorizacionServicio, '3': FotoFormulaMedica,
                                                 '4': AvisoDireccion, '5': EligeMunicipio,
                                                 '6': DireccionBarrio, '7': DigitaCelular,
                                                 '8': DigitaCorreo})

    def test_first_step(self):
        request = get_request()
        testform = TestWizard.as_view(FORMS)
        response, instance = testform(request)
        self.assertEqual(instance.steps.current, 'home')

    def test_persistence(self):
        """Test the order of some steps"""
        testform = TestWizard.as_view(FORMS)
        # Se le hace un post a la vista de home
        request = get_request({'test_wizard-current_step': 'home'})
        response, instance = testform(request)
        self.assertEqual(instance.steps.current, 'instrucciones')

        instance.storage.current_step = 'instrucciones'

        testform2 = TestWizard.as_view(FORMS)
        request.POST = {'test_wizard-current_step': 'instrucciones'}
        response, instance = testform2(request)
        self.assertEqual(instance.steps.current, 'autorizacionServicio')

    def test_form_prefix(self):
        request = get_request()
        testform = TestWizard.as_view(FORMS)
        response, instance = testform(request)
        self.assertEqual(instance.get_form_prefix(), 'home')
        self.assertEqual(instance.get_form_prefix('another'), 'another')

    def test_done(self):
        request = get_request()
        testform = TestWizard.as_view(FORMS)
        response, instance = testform(request)
        self.assertTrue(instance.done)

