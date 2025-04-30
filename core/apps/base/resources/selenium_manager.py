"""Create a singleton manager to ensure a single instance of Selenium."""

from RPA.Browser.Selenium import Selenium  # type: ignore
from selenium import webdriver


class LoginPage:
    def visit(self, browser, url):
        browser.go_to(url)

    def perform(self, url: str, browser: Selenium):
        self.visit(browser, url)
        # Select tipo de usuario

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
