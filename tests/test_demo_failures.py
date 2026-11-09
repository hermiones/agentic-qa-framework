"""Intentionally failing tests that show the classifier at work.

Skipped by default (CI stays green). Run them with:  DEMO_FAILURES=1 pytest
Each one fails for a different reason and lands in a different bucket.
"""
import pytest

from framework import data
from framework.assertions import expect_business
from framework.pages import DashboardPage, ReportsPage

pytestmark = pytest.mark.demo_failure


@pytest.mark.req("REQ-015")
def test_demo_product_defect_online_kpi(viewer_page):
    """The demo app counts 'maintenance' meters as online: a real product bug -> product_defect."""
    dash = DashboardPage(viewer_page).open()
    expect_business(dash.kpi("online"), sum(m["status"] == "online" for m in data.meters()), "online meters KPI")


@pytest.mark.req("REQ-022")
def test_demo_ui_change_export_button_renamed(admin_page):
    """The test still uses an old locator (#export-btn) after the UI renamed it -> ui_change."""
    ReportsPage(admin_page).open()
    admin_page.locator("#export-btn").click(timeout=2000)


@pytest.mark.req("REQ-023")
def test_demo_environment_dependency_down(playwright):
    """A downstream service is not running -> environment, not a product bug."""
    ctx = playwright.request.new_context(base_url="http://127.0.0.1:9")
    try:
        ctx.get("/billing/health")
    finally:
        ctx.dispose()
