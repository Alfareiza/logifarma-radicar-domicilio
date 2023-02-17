from core.apps.base.tests.utilities import VisualWizardTests


class AllFLow(VisualWizardTests):

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

    # def test_1_autorizacion_0_btn_continuar(self):
    #     boton_continuar = self.get_boton_continuar()
    #     self.assertTrue(boton_continuar, 'No se encontró el botón continuar')
    #     self.assertEqual(boton_continuar.text, 'Continuar')

    # def test_1_autorizacion_1_btn_animacion(self):
    #     animacion = self.get_animacion()
    #     self.assertTrue(animacion, 'No se encontró la animación')
    #     self.assertEqual(animacion.value_of_css_property('display'), 'none', "Animación aparece al entrar en home")
    #     self.insert_data(value="autorizacionServicio-num_autorizacion", data='99999999')
    #     self.assertTrue(self.animacion_works(animacion, id_btn='btn_con'),
    #                     "Animación no aparece al clicar en continuar")

    # def test_1_autorizacion_2_btn_atras(self):
    #     boton_atras = self.get_boton_atras()
    #     self.assertTrue(boton_atras, 'No se encontró el botón atrás')
    #     self.assertEqual(boton_atras.text, '< Atrás')
    #     boton_atras.click()
    #     self.assertEqual(self.selenium.title, 'Instrucciones')
    #     self.process_instrucciones()

    # def test_1_autorizacion_2_ingresando_99_999_9999_y_enter_next_step(self):
    #     num_aut_box = self.selenium.find_element(by=By.NAME, value="autorizacionServicio-num_autorizacion")
    #     num_aut_box.send_keys("99999999")
    #     # Por algún motivo al darle enter se va a la vista de Instrucciones
    #     num_aut_box.send_keys(Keys.ENTER)
    #     if self.selenium.title == 'Instrucciones':
    #         self.get_boton_continuar().click()
    #     num_aut_box = self.selenium.find_element(by=By.NAME, value="autorizacionServicio-num_autorizacion")
    #     num_aut_box.send_keys("99999999")
    #     num_aut_box.send_keys(Keys.ENTER)
    #     self.assertEqual(self.selenium.title, 'Foto de la fórmula')

    def test_1_autorizacion_3_connect_to_foto(self):
        self.process_autorizacion()
        self.assertEqual(self.selenium.title, 'Foto de la fórmula')

    def test_2_foto(self):
        print(f'===== TESTING ===== > {self.selenium.title}')
        title = self.selenium.title
        self.assertEqual(title, 'Foto de la fórmula')

    def test_2_foto_0_connect_elige_municipio(self):
        self.process_foto()
        self.assertEqual(self.selenium.title, 'Elige Municipio')

    def test_3_elige_municipio_1_connect_to_direccion_barrio(self):
        self.process_elige_municipio()
        self.assertEqual(self.selenium.title, 'Elige el barrio')

    def test_4_direccion_barrio(self):
        print(f'===== TESTING ===== > {self.selenium.title}')
        title = self.selenium.title
        self.assertEqual(title, 'Elige el barrio')

    def test_4_direccion_barrio_0_connect_to_celular(self):
        self.process_direccion_barrio()
        self.assertEqual(self.selenium.title, 'Digite celular')

    def test_5_celular(self):
        print(f'===== TESTING ===== > {self.selenium.title}')
        title = self.selenium.title
        self.assertEqual(title, 'Digite celular')

    def test_5_celular_0_connect_to_correo(self):
        self.process_celular()
        self.assertEqual(self.selenium.title, 'Digite un correo electrónico')

    def test_6_correo(self):
        print(f'===== TESTING ===== > {self.selenium.title}')
        title = self.selenium.title
        self.assertEqual(title, 'Digite un correo electrónico')

    def test_6_correo_0_connect_to_done(self):
        self.process_correo()
        self.assertEqual(self.selenium.title, 'Listo')

    def test_7_finalizado(self):
        print(f'===== TESTING ===== > {self.selenium.title}')
        title = self.selenium.title
        self.assertEqual(title, 'Listo')

    def test_7_finalizado_0_connect_to_home(self):
        self.process_finalizado()
        self.assertEqual(self.selenium.title, 'Domicilios Logifarma')
