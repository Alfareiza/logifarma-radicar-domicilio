from core.apps.base.tests.utilities import VisualWizardTests
from core.apps.base.views import FORMS


class AllFLow(VisualWizardTests):
    map_vistas = [
        {'Inicio': 'self.process_home()'},
        {
            'Autorización de servicio': "self.process_autorizacion(number='99_999_998', expected_step=('Elige Municipio','eligeMunicipio'))"},
        {'Elige Municipio': 'self.process_elige_municipio()'},
        {'Elige el barrio': 'self.process_direccion_barrio()'},
        {'Digite celular': 'self.process_celular()'},
        {'Digite un correo electrónico': 'self.process_correo()'},
        {'Listo': 'self.process_correo()'},
    ]

    vistas = [ele[0] for ele in FORMS]
    vistas.remove('fotoFormulaMedica')

    def test_0_home(self):
        self.selenium.get(f'{self.live_server_url}/')
        print(f'===== TESTING ===== > {self.selenium.title}')
        title = self.selenium.title
        self.assertEqual(title, 'Domicilios Logifarma')

    # def test_0_home_0_btn_continuar(self):
    #     boton_continuar = self.get_boton_continuar()
    #     self.assertTrue(boton_continuar, 'No se encontró el botón continuar')
    #     self.assertEqual(boton_continuar.text, 'Continuar')

    # def test_0_home_1_animacion(self):
    #     animacion = self.get_animacion()
    #     self.assertTrue(animacion, 'No se encontró la animación')
    #     self.assertEqual(animacion.value_of_css_property('display'), 'none', "Animación aparece al entrar en home")
    #     self.assertTrue(self.animacion_works(animacion), "Animación no aparece al clicar en continuar")

    def test_0_home_1_connect_to_autorizacion(self):
        self.process_home()
        title = self.selenium.title
        self.assertEqual(title, 'Autorización de servicio')

    def test_1_autorizacion(self):
        print(f'===== TESTING ===== > {self.selenium.title}')
        title = self.selenium.title
        self.assertEqual(title, 'Autorización de servicio')

    def test_1_autorizacion_3_connect_to_elige_municipio(self):
        self.process_autorizacion(number='99999998', expected_step=('Elige Municipio', 'eligeMunicipio'))
        self.assertEqual(self.selenium.title, 'Elige Municipio')

    def test_2_elige_municipio_1_connect_to_direccion_barrio(self):
        self.process_elige_municipio()
        self.assertEqual(self.selenium.title, 'Elige el barrio')

    def test_3_direccion_barrio(self):
        print(f'===== TESTING ===== > {self.selenium.title}')
        title = self.selenium.title
        self.assertEqual(title, 'Elige el barrio')

    def test_3_direccion_barrio_0_connect_to_celular(self):
        self.process_direccion_barrio()
        self.assertEqual(self.selenium.title, 'Digite celular')

    def test_4_celular(self):
        print(f'===== TESTING ===== > {self.selenium.title}')
        title = self.selenium.title
        self.assertEqual(title, 'Digite celular')

    def test_4_celular_0_connect_to_correo(self):
        self.process_celular()
        self.assertEqual(self.selenium.title, 'Digite un correo electrónico')

    def test_5_correo(self):
        print(f'===== TESTING ===== > {self.selenium.title}')
        title = self.selenium.title
        self.assertEqual(title, 'Digite un correo electrónico')

    def test_5_correo_0_connect_to_done(self):
        self.process_correo()
        self.assertEqual(self.selenium.title, 'Listo')

    def test_6_finalizado(self):
        print(f'===== TESTING ===== > {self.selenium.title}')
        title = self.selenium.title
        self.assertEqual(title, 'Listo')

    def test_6_finalizado_0_connect_to_home(self):
        self.process_finalizado()
        self.assertEqual(self.selenium.title, 'Domicilios Logifarma')
