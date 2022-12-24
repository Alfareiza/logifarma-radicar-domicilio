from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


class MySeleniumTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.selenium = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def get_boton_continuar(self):
        return self.selenium.find_element(by=By.CLASS_NAME, value='btn')

    def get_animacion(self):
        return self.selenium.find_element(by=By.ID, value='btn_carga')

    def get_boton_atras(self):
        return self.selenium.find_element(by=By.CLASS_NAME, value='atras')

    def animacion_works(self, animacion, id_btn='btn_conti'):
        self.selenium.execute_script(f'document.getElementById("{id_btn}").click(); window.stop()')
        works = animacion.value_of_css_property('display') == 'block'
        self.selenium.execute_script('window.location.reload()')
        return works

    def test_0_home(self):
        self.selenium.get(f'{self.live_server_url}/')

        print(f'===== TESTING ===== > {self.selenium.title}')
        title = self.selenium.title
        self.assertEqual(title, 'Inicio')

        boton_continuar = self.get_boton_continuar()
        self.assertTrue(boton_continuar, 'No se encontró el botón continuar')
        self.assertEqual(boton_continuar.text, 'Continuar')

        animacion = self.get_animacion()
        self.assertTrue(animacion, 'No se encontró la animación')
        self.assertEqual(animacion.value_of_css_property('display'), 'none', "Animación aparece al entrar en home")

        self.assertTrue(self.animacion_works(animacion), "Animación no aparece al clicar en continuar")

        self.get_boton_continuar().click()

    def test_1_instrucciones(self):
        print(f'===== TESTING ===== > {self.selenium.title}')

        title = self.selenium.title
        self.assertEqual(title, 'Instrucciones')

        boton_continuar = self.get_boton_continuar()
        self.assertTrue(boton_continuar, 'No se encontró el botón continuar')
        self.assertEqual(boton_continuar.text, 'Continuar')

        animacion = self.get_animacion()
        self.assertTrue(animacion, 'No se encontró la animación')
        self.assertEqual(animacion.value_of_css_property('display'), 'none', "Animación aparece al entrar en home")

        self.assertTrue(self.animacion_works(animacion), "Animación no aparece al clicar en continuar")

        # Probando botón atrás
        boton_atras = self.get_boton_atras()
        self.assertTrue(boton_atras, 'No se encontró el botón atrás')
        self.assertEqual(boton_atras.text, '< Atrás')
        boton_atras.click()
        self.assertEqual(self.selenium.title, 'Inicio')
        self.get_boton_continuar().click()

        self.get_boton_continuar().click()

    def test_2_autorizacion(self):
        print(f'===== TESTING ===== > {self.selenium.title}')

        title = self.selenium.title
        self.assertEqual(title, 'Autorización de servicio')

    def test_2_autorizacion_0_btn_continuar_y_animacion(self):
        boton_continuar = self.get_boton_continuar()
        self.assertTrue(boton_continuar, 'No se encontró el botón continuar')
        self.assertEqual(boton_continuar.text, 'Continuar')

        animacion = self.get_animacion()
        self.assertTrue(animacion, 'No se encontró la animación')
        self.assertEqual(animacion.value_of_css_property('display'), 'none', "Animación aparece al entrar en home")

        num_aut_box = self.selenium.find_element(by=By.NAME, value="autorizacionServicio-num_autorizacion")
        num_aut_box.send_keys("99999999")
        self.assertTrue(self.animacion_works(animacion, id_btn='btn_con'),
                        "Animación no aparece al clicar en continuar")
        self.get_boton_continuar().click()

    def test_2_autorizacion_1_btn_atras(self):
        boton_atras = self.get_boton_atras()
        self.assertTrue(boton_atras, 'No se encontró el botón atrás')
        self.assertEqual(boton_atras.text, '< Atrás')
        boton_atras.click()
        self.assertEqual(self.selenium.title, 'Instrucciones')
        self.get_boton_continuar().click()

    def test_2_autorizacion_2_ingresando_99_999_9999_y_enter(self):
        num_aut_box = self.selenium.find_element(by=By.NAME, value="autorizacionServicio-num_autorizacion")
        num_aut_box.send_keys("99999999")
        # Por algún motivo al darle enter se va a la vista de Instrucciones
        num_aut_box.send_keys(Keys.ENTER)
        if self.selenium.title == 'Instrucciones':
            self.get_boton_continuar().click()
        num_aut_box = self.selenium.find_element(by=By.NAME, value="autorizacionServicio-num_autorizacion")
        num_aut_box.send_keys("99999999")
        num_aut_box.send_keys(Keys.ENTER)
        self.assertEqual(self.selenium.title, 'Foto de la fórmula')

    def test_3_foto(self):
        print(f'===== TESTING ===== > {self.selenium.title}')

        title = self.selenium.title
        self.assertEqual(title, 'Foto de la fórmula')

#TODO
# Probar en la vista de done.html que no pueda el usuario devolverse
# window.history.go(-1);
