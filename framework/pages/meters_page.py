from .base_page import BasePage


class MetersPage(BasePage):
    path = "/meters"

    def __init__(self, page):
        super().__init__(page)
        self.search_box = page.get_by_test_id("meter-search")
        self.status_filter = page.get_by_test_id("status-filter")
        self.count_label = page.get_by_test_id("meter-count")
        self.rows = page.get_by_test_id("meter-row")
        self.visible_rows = page.locator("[data-testid=meter-row]:not([hidden])")

    def search(self, text: str):
        self.search_box.fill(text)
        return self

    def filter_status(self, status: str):
        self.status_filter.select_option(status)
        return self

    def visible_statuses(self) -> list[str]:
        return [s.strip() for s in self.visible_rows.get_by_test_id("meter-status").all_inner_texts()]

    def open_meter(self, meter_id: str):
        self.page.get_by_role("link", name=meter_id, exact=True).click()
