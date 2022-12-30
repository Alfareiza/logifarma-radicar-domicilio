from django.test import TestCase
from django.urls import reverse

from core.apps.base.forms import *
from core.apps.base.tests.utilities import get_request, TestWizard, TestWizardWithInitAttrs
from core.apps.base.views import FORMS


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
