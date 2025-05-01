"""Create a singleton manager to ensure a single instance of Selenium."""
import datetime
import logging
from time import sleep

from RPA.Browser.Selenium import Selenium  # type: ignore
from selenium import webdriver

logger = logging.getLogger(__name__)

def wait_element_load(browser, locator, timeout=5):
    is_success = False
    timer = datetime.datetime.now() + datetime.timedelta(0, timeout)

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
        browser.input_text(self.nit, "900073223")
        browser.input_text(self.usuario, "9000732235")
        browser.input_text(self.clave, "900073223")

    def perform(self, url: str, browser: Selenium):
        logger.info('Accesando a site Mutual Ser')
        self.visit(browser, url)
        # Select tipo de usuario
        browser.click_element(self.dropdown_tipo_usuario)
        logger.info('Site cargó exitosamente, esperando ver botón de tipo de usuario.')
        browser.get_webelement(self.dropdown_prestador).click()
        if not wait_element_load(browser, self.nit):
            raise AssertionError('Botón de NIT no apareció después de clicar en Prestador')
        logger.info('Ingresando credenciales.')
        self.input_credentials(browser)
        logger.info('Credenciales ingresadas.')
        browser.click_element(self.iniciar_sesion)
        logger.info('Clicando en iniciar sesión.... esperando')
        if browser.does_page_contain_element("//h3[text()='Modulos Portal']"):
            logger.info('Login efectuado con éxito.')



class BaseApp:
    """Base class for application or portal objects and their configuration."""

    browser: Selenium = Selenium
    headless: bool = False
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
    headless: bool = False
    login = LoginPage()
    wait_time: int = 2
    browser_options = ["--no-sandbox", "--disable-dev-shm-usage",
                       "--log-level=3", "--disable-logging",
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
