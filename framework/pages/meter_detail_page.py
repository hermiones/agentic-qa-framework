from .base_page import BasePage


class MeterDetailPage(BasePage):
    def __init__(self, page):
        super().__init__(page)
        self.meter_id = page.get_by_test_id("meter-id")
        self.status = page.get_by_test_id("meter-status")
        self.readings = page.get_by_test_id("reading-row")
        self.total = page.get_by_test_id("total-kwh")

    def open_meter(self, meter_id: str):
        self.page.goto(f"/meters/{meter_id}")
        return self

    def total_kwh(self) -> float:
        return float(self.total.inner_text().replace("kWh", "").strip())
