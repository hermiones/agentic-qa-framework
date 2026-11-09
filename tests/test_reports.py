"""Reports: admin-only, with business totals and CSV export."""
import csv
import io

import pytest
from playwright.sync_api import expect

from framework import data
from framework.assertions import expect_business
from framework.pages import ReportsPage


@pytest.mark.req("REQ-020")
def test_admin_report_total_matches_seed_data(admin_page):
    report = ReportsPage(admin_page).open().generate()
    expected = round(sum(data.total_kwh(m) for m in data.meters()), 1)
    expect(report.total).to_be_visible()
    expect_business(report.total_kwh(), expected, "report total consumption (kWh)", tolerance=0.05)


@pytest.mark.req("REQ-021")
def test_viewer_cannot_open_reports(viewer_page):
    report = ReportsPage(viewer_page).open()
    expect(report.access_denied).to_contain_text("admins only")
    expect(report.generate_link).to_have_count(0)


@pytest.mark.req("REQ-022")
def test_csv_export_has_one_row_per_meter(admin_api):
    resp = admin_api.get("/reports/export.csv")
    assert resp.ok, f"export failed with HTTP {resp.status}"
    rows = list(csv.DictReader(io.StringIO(resp.text())))
    assert list(rows[0].keys()) == ["meter_id", "location", "status", "total_kwh"]
    expect_business(len(rows), len(data.meters()), "rows in CSV export")
