"""Module for BaseApp class."""

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
        self.page.open_browser()
        self.page.login.perform(self.url, self.browser)
        self.browser.close_all_browsers()


if __name__ == '__main__':
    site = MutualSerPage('https://portal.mutualser.org/ZONASER/home.xhtml')
    site.login()