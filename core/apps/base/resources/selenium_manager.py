"""Create a singleton manager to ensure a single instance of Selenium."""
import datetime
import logging
import re
from time import sleep

from RPA.Browser.Selenium import Selenium
from SeleniumLibrary.errors import ElementNotFound
from bs4 import BeautifulSoup, Tag
from retry import retry
from selenium import webdriver
from selenium.common import StaleElementReferenceException, ElementNotInteractableException, \
    ElementClickInterceptedException

from core.apps.base.exceptions import UserNotFound, NroAutorizacionNoEncontrado, NoRecordsInTable, FieldError, \
    NoImageWindow
from core.apps.tasks.utils.dt_utils import Timer

from core.settings import logger as log, ZONA_SER_NIT


def wait_element_load(browser, locator, timeout=5):
    is_success = False
    timer = datetime.datetime.now() + datetime.timedelta(0, seconds=timeout)

    while not is_success and timer > datetime.datetime.now():
        if browser.does_page_contain_element(locator):
            try:
                elem = browser.find_element(locator)
                is_success = elem.is_displayed()
            except Exception:
                sleep(1)

    if not is_success:
        return False
    return True


class LoginPage:
    dropdown_tipo_usuario = "//div[contains(@id, 'formLogin:listBoxTipoUsuario')]"
    dropdown_prestador = "//div[@id='formLogin:listBoxTipoUsuario_panel']//li[text()='Prestador']"
    nit = "//input[@id='formLogin:nit']"
    usuario = "//input[@id='formLogin:usuario']"
    clave = "//input[@id='formLogin:contraseña']"
    iniciar_sesion = "//button[@id='formLogin:loginButton']"

    def visit(self, browser, url):
        browser.go_to(url)
        wait_element_load(browser, self.dropdown_tipo_usuario)

    def input_credentials(self, browser: Selenium):
        browser.input_text(self.nit, ZONA_SER_NIT)
        browser.input_text(self.usuario, f"{ZONA_SER_NIT}5")
        browser.input_text(self.clave, ZONA_SER_NIT)

    def perform(self, url: str, browser: Selenium):
        log.info('Accesando a site Mutual Ser')
        self.visit(browser, url)
        # Select tipo de usuario
        browser.click_element(self.dropdown_tipo_usuario)
        # log.info('Site cargó exitosamente, esperando ver botón de tipo de usuario.')
        browser.get_webelement(self.dropdown_prestador).click()
        if not wait_element_load(browser, self.nit):
            raise AssertionError('Botón de NIT no apareció después de clicar en Prestador')
        # log.info('Ingresando credenciales')
        self.input_credentials(browser)
        # log.info('Credenciales ingresadas')
        browser.click_element(self.iniciar_sesion)
        # log.info('Clicando en iniciar sesión.... esperando')
        if wait_element_load(browser, "//h3[text()='Modulos Portal']"):
            log.info('Login efectuado con éxito.')


class SearchPage:
    consulta_solicitudes = "//*[@id='main:j_idt29']//span[text()='Consulta de Solicitudes']"
    solicitud_de_autorizacion = "//label[text()[contains(., 'autorización de servicios')]]"
    afiliado_dropdown = "//div[@id='main:tipoAfiliadoSolicitud']"
    afiliado_tipo_documento = "//div[@id='main:tipoAfiliadoSolicitud_panel']//li[text()='{}']"
    afiliado_documento = "//input[@id='main:documentoAfiliadoSolicitud']"
    buscar_btn = "//img[contains(@src, 'buscar1.gif')]"
    table = "//table[thead[@id='main:a3tabladesolicuti_head']]"
    lupa_link = "//tr[td/span[contains(normalize-space(), 'Ver solicitud:')]]/td[2]/a"
    confirmar_fecha_prest = '//span[contains(text(), "Confirmar Fecha Prest")]'
    fecha_prestacion = "//input[contains(@name, 'fechaPrestacion_input')]"
    nro_para_facturar = '//span[contains(text(), "El Nro. para Facturar es: ")]'
    close_modal = "//div[@id='main:detallesolicitud']//a[@role='button'][span[contains(@class, 'ui-icon-closethick')]]"
    calendar_icon = "//div[@id='main:pnlPrestacion']//button[@type='button'][.//span[contains(@class, 'ui-icon-calendar')]]"
    day_icon = "//div[@id='ui-datepicker-div']//td[a[text()='{day}']]"
    table_productos = "//div[@id='main:tableDetProductos']"
    detalle_factura_modal = '//div[@id="main:detalleFacturas"]'
    nro_para_facturar_en_modal_detalle_factura = "//span[contains(@id, 'numFacturarConcurrencia')]"

    def goto_form(self, browser):
        browser.click_element(self.consulta_solicitudes)
        wait_element_load(browser, self.solicitud_de_autorizacion)
        browser.click_element(self.solicitud_de_autorizacion)
        wait_element_load(browser, self.afiliado_dropdown)

    def input_info_afiliado(self, browser, tipo_documento, documento):
        global locator_tipo_documento
        try:
            browser.click_element(self.afiliado_dropdown)
            locator_tipo_documento = self.afiliado_tipo_documento.format(tipo_documento)
            browser.get_webelement(locator_tipo_documento).click()
            browser.input_text(self.afiliado_documento, documento)
            wait_element_load(browser, self.buscar_btn)
        except ElementNotFound as e:
            if locator_tipo_documento in str(e):
                raise FieldError(f"{tipo_documento} no encontrado en formulario.") from e
            raise

    @retry(ElementNotInteractableException, tries=3, delay=1)
    def close_modal_detalle_solicitud(self, browser):
        browser.click_element(self.close_modal)

    def click_ver(self, browser, row):
        """Si el botón de "Ver" que está en la última columna está clicable, entonces lo clica."""
        if 'Número para Facturar:Ver' not in row.get_text(strip=True):
            log.info("Botón de 'Ver' no está presente en esta fila")
            return ''
        label_td = row.find('td', string=lambda text: text and 'Número para Facturar' in text)
        link_ver = label_td.find_next_sibling('td').find('a')['id']
        browser.driver.execute_script(f"document.getElementById('{link_ver}').click();")
        wait_element_load(browser, self.detalle_factura_modal)
        wait_element_load(browser, self.nro_para_facturar_en_modal_detalle_factura)
        nro_para_facturar = browser.get_text(self.nro_para_facturar_en_modal_detalle_factura)
        close_modal = f"{self.detalle_factura_modal}//a[contains(@class, 'ui-dialog-titlebar-close')]"
        browser.click_element(close_modal)
        wait_element_load(browser, self.buscar_btn)
        log.info(f"Nro de autorización {nro_para_facturar} encontrado en botón de 'Ver'")
        return nro_para_facturar

    @retry(NoRecordsInTable, tries=3, delay=2)
    def extract_productos(self, browser):
        """Extrae los productos que estan en la tabla del modal."""
        productos_html = browser.find_element(self.table_productos)
        html_table = BeautifulSoup(productos_html.get_attribute("outerHTML"), "html.parser")
        table = html_table.find('table')
        headers = [th.text.strip() for th in table.thead.find_all('th')]
        rows = []
        for tr in table.tbody.find_all('tr'):
            cells = tr.find_all('td')
            values = [td.get_text(strip=True).replace(';', '') for td in cells]
            for value in values:
                if 'No records found' in value:
                    raise NoRecordsInTable
            row_dict = dict(zip(headers, values))
            rows.append(row_dict)
        return rows

    def wait_until_new_window_opens(self, browser, seconds: int):
        """Espera 5 segundos hasta que una nueva ventana exista."""
        timer = Timer(seconds)
        while timer.not_expired:
            if len(browser.driver.window_handles) > 1:
                return

        raise NoImageWindow(f"No cargó ventana con información de autorización en {seconds} segundos.")

    def switch_window(self, browser):
        """Simula el comportamiento de ALT+TAB entre 2 ventanas."""
        for _ in range(5):
            current_window = browser.driver.current_window_handle
            if len(browser.driver.window_handles) == 1:
                return
            for window in browser.driver.window_handles:
                if window == current_window:
                    continue
                browser.driver.switch_to.window(window)
                return
            sleep(1)
        raise NoImageWindow

    def get_img_url(self, browser, row):
        """Si se encuentra el botón que diga 'N° Aprobación' procede a capturar su url."""
        if 'Aprobación' not in row.get_text(strip=True):
            log.info("Botón de 'Ver' no está presente en esta fila")
            return ''
        label_td = row.find('td', string=lambda text: text and 'N° Aprobación:' in text)
        link_ver = label_td.find_next_sibling('td').find('a')['id']
        browser.driver.execute_script(f"document.getElementById('{link_ver}').click();")
        self.wait_until_new_window_opens(browser, 5)
        self.switch_window(browser)
        img_url = browser.driver.current_url
        self.switch_window(browser)
        # browser.driver.close()
        return img_url

    def extract_extra_info(self, browser, row: Tag):
        """Extra el numero de autorizacion y medicamentos."""
        nro_para_facturar = self.click_ver(browser, row)  # A veces el nro para facturar está al clicar en Ver

        label_td = row.find('td', string=lambda text: text and 'Ver solicitud' in text)
        link_lupa = label_td.find_next_sibling('td').find('a')['id']
        browser.driver.execute_script(f"document.getElementById('{link_lupa}').click();")

        if not nro_para_facturar:
            nro_para_facturar = self.extract_nro_para_facturar_modal_lupa(browser)
        if not nro_para_facturar:
            raise NroAutorizacionNoEncontrado

        productos = self.extract_productos(browser)
        self.close_modal_detalle_solicitud(browser)

        if match := re.search(r'El Nro\. para Facturar es:\s*([A-Z0-9]+)', nro_para_facturar):
            nro_para_facturar = re.findall(r'\d+', match[1])[0]

        return nro_para_facturar, productos

    def extract_nro_para_facturar_modal_lupa(self, browser):
        log.info("Buscando nro para facturar en opción de lupa")
        wait_element_load(browser, self.confirmar_fecha_prest)
        browser.click_element(self.calendar_icon)
        self.day_icon = self.day_icon.format(day=datetime.datetime.now().day)
        browser.scroll_element_into_view(self.day_icon)
        browser.click_element(self.day_icon)
        browser.click_element(self.confirmar_fecha_prest)
        wait_element_load(browser, self.nro_para_facturar)
        return browser.get_text(self.nro_para_facturar)

    def scrap_table(self, browser, tipo_documento, documento):
        """Navega a lo largo de las filas que están en el resultado del afiliado."""
        table_element = browser.find_element(self.table)
        rows_info = []
        html_table = BeautifulSoup(table_element.get_attribute("outerHTML"), "html.parser")
        rows = html_table.find('tbody').find_all('tr', recursive=False)
        for i, row in enumerate(rows, 1):
            estado = row.contents[7].find_all("option", selected=True)[-1].text
            match = re.search(r"Numero solicitud:(\d+)Fecha Solicitud:(\d{2}/\d{2}/\d{4})",
                              row.contents[3].get_text(strip=True))
            if estado.upper() == 'APROBADO':
                log.info(f'Obteniendo información de fila {i}')
                img_orden_url = self.get_img_url(browser, row)
                nro_para_facturar, productos = self.extract_extra_info(browser, row.contents[-1])
            else:
                log.info(f'Ignorando fila {i} por que autorización está {estado.upper()!r}')
                # En caso se aplique alguna lógica para cuando sea diferente de APROBADO
                # nro_para_facturar, productos = [], ''
                continue

            rows_info.append({
                'TIPO_DOCUMENTO': tipo_documento,
                'DOCUMENTO': documento,
                'CONSECUTIVO_PROCEDIMIENTO': row.contents[2].text,
                'NUMERO_SOLICITUD': match[1] if match else '',
                'FECHA_SOLICITUD': match[2] if match else '',
                'ESTADO_AUTORIZACION': estado,
                'NUMERO_AUTORIZACION': nro_para_facturar,
                'DISPENSADO': None,
                'URL_ORDEN': img_orden_url,
                'DETALLE_AUTORIZACION': [{'NOMBRE_PRODUCTO': producto['Tecnologías'], 'CANTIDAD': producto['Cantidad']}
                                         for producto in productos]
            })
            log.info(f'Fila {i} procesada con éxito.')
        return rows_info

    def extract_table(self, browser, tipo_documento, documento):
        try:
            return self.scrap_table(browser, tipo_documento, documento)
        except (StaleElementReferenceException, ElementNotFound, ElementNotInteractableException,
                ElementClickInterceptedException) as exc:
            import traceback
            traceback.print_exc()
            browser.capture_page_screenshot('psi.png')
            # TODO send email
            raise

    def perform(self, browser, tipo_documento, documento):
        """Busca usuario en mutual ser, este paso asume que el login ha sido efectuado."""
        self.goto_form(browser)
        self.input_info_afiliado(browser, tipo_documento, documento)
        browser.click_element(self.buscar_btn)
        if not wait_element_load(browser, "//*[contains(text(),'la consulta realizada arroja las solicitudes')]", 2):
            log.info('No apareció mensaje ... la consulta realizada arroja las solicitudes de autorización y por eso'
                     ' no se pudo comprobar si la página cargó después de clicar en buscar.')
        if browser.does_page_contain("No se encontraron registros"):
            raise UserNotFound(f'No fue encontrado usuario con {tipo_documento.lower()} {documento} en mutual ser.')
        return self.extract_table(browser, tipo_documento, documento)


class BaseApp:
    """Base class for application or portal objects and their configuration."""

    browser: Selenium = Selenium
    headless: bool = True
    wait_time: int = 10
    # download_directory: str = str(Path().cwd() / Path("temp"))
    browser_options: list = ["--no-sandbox", "--disable-dev-shm-usage"]
    experimental_options: dict = {
        "excludeSwitches": ["enable-automation"],
        "useAutomationExtension": False,
    }
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    )

    def open_browser(self) -> None:
        """Open browser and set Selenium options."""
        browser_options = webdriver.ChromeOptions()

        for option in self.browser_options:
            browser_options.add_argument(option)

        for key, value in self.experimental_options.items():
            browser_options.add_experimental_option(key, value)

        if self.headless:
            browser_options.add_argument("--headless")

        self.browser.set_selenium_implicit_wait(self.wait_time)
        # self.browser.set_download_directory(self.download_directory)
        self.browser.open_available_browser(user_agent=self.user_agent, options=browser_options, maximized=True)


class MutualSerSite(BaseApp):
    """Main application class managing pages and providing direct access to Selenium."""

    browser: Selenium = None
    login = LoginPage()
    search_page = SearchPage()
    wait_time: int = 2
    browser_options = ["--no-sandbox", "--disable-dev-shm-usage",
                       "--log-level=3",
                       # "--disable-logging",
                       "--lang=en"]
    experimental_options = {
        "excludeSwitches": ("enable-automation",),
        "useAutomationExtension": False,
    }

    def __init__(self, **config) -> None:
        """Initialize Involve class with default configuration."""
        super().__init__(**config)
        self.browser = Selenium()
        self.browser.set_selenium_implicit_wait(0)
