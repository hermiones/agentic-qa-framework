import re

from .base_page import BasePage


class ReportsPage(BasePage):
    path = "/reports"

    def __init__(self, page):
        super().__init__(page)
        self.generate_link = page.get_by_test_id("generate-report")
        self.total = page.get_by_test_id("report-total")
        self.export_link = page.get_by_test_id("export-csv")
        self.access_denied = page.get_by_test_id("access-denied")

    def generate(self):
        self.generate_link.click()
        return self

    def total_kwh(self) -> float:
        return float(re.search(r"([\d.]+)\s*kWh", self.total.inner_text()).group(1))
