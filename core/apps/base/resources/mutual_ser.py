"""Module for BaseApp class."""
from datetime import datetime

from RPA.Browser.Selenium import Selenium  # type: ignore

from core.apps.base.resources.selenium_manager import MutualSerSite


class MutualSerPage:
    def __init__(self, url: str):
        self.url = url
        self.page = MutualSerSite()

    @property
    def browser(self):
        return self.page.browser

    def login(self):
        print(f'{datetime.now():%T:%s} - INIT PROCESS')
        self.page.open_browser()
        self.page.login.perform(self.url, self.browser)
        self.search_user()
        print(f'{datetime.now():%T:%s} - END PROCESS')
        self.browser.close_all_browsers()

    def search_user(self):
        self.page.search_page.perform(self.browser, 'Cedula de Ciudadania', '32816865')





if __name__ == '__main__':
    site = MutualSerPage('https://portal.mutualser.org/ZONASER/home.xhtml')
    site.login()