"""Base page: navigation + a few shared locators. All locators use data-testid and
Playwright's auto-waiting, so there are no sleeps anywhere in the framework."""
from playwright.sync_api import Page


class BasePage:
    path = "/"

    def __init__(self, page: Page):
        self.page = page
        self.current_user = page.get_by_test_id("current-user")

    def open(self):
        self.page.goto(self.path)
        return self

    def by_id(self, test_id: str):
        return self.page.get_by_test_id(test_id)
