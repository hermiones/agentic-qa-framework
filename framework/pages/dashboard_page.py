from .base_page import BasePage


class DashboardPage(BasePage):
    path = "/dashboard"

    def __init__(self, page):
        super().__init__(page)
        self.welcome = page.get_by_test_id("welcome")

    def kpi(self, name: str) -> int:
        """Read a KPI tile (total / online / offline) as an int."""
        return int(self.by_id(f"kpi-{name}").inner_text().strip())
