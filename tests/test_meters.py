"""Meters list and detail, verified against the seed data (the test oracle)."""
import pytest
from playwright.sync_api import expect

from framework import data
from framework.assertions import expect_business
from framework.pages import DashboardPage, MeterDetailPage, MetersPage


@pytest.mark.req("REQ-010")
def test_meter_list_shows_every_seeded_meter(viewer_page):
    meters = MetersPage(viewer_page).open()
    expect(meters.rows).to_have_count(len(data.meters()))
    expect(meters.count_label).to_have_text(f"Showing {len(data.meters())} meters")


@pytest.mark.req("REQ-011")
def test_search_filters_by_location(viewer_page):
    meters = MetersPage(viewer_page).open().search("Kolkata")
    expected = [m for m in data.meters() if "kolkata" in m["location"].lower()]
    expect(meters.visible_rows).to_have_count(len(expected))


@pytest.mark.req("REQ-012")
def test_status_filter_shows_only_offline_meters(viewer_page):
    meters = MetersPage(viewer_page).open().filter_status("offline")
    expected = sum(1 for m in data.meters() if m["status"] == "offline")
    expect(meters.visible_rows).to_have_count(expected)
    assert set(meters.visible_statuses()) == {"offline"}


@pytest.mark.req("REQ-013")
@pytest.mark.parametrize("meter_id", ["MTR-1001", "MTR-1004"])
def test_meter_total_equals_sum_of_readings(viewer_page, meter_id):
    seeded = data.meter(meter_id)
    detail = MeterDetailPage(viewer_page).open_meter(meter_id)
    expect(detail.readings).to_have_count(len(seeded["readings"]))
    expect_business(detail.total_kwh(), data.total_kwh(seeded), f"{meter_id} total consumption (kWh)", tolerance=0.05)


@pytest.mark.req("REQ-014")
def test_dashboard_offline_kpi_matches_seed_data(viewer_page):
    dash = DashboardPage(viewer_page).open()
    expect_business(dash.kpi("total"), len(data.meters()), "total meters KPI")
    expect_business(dash.kpi("offline"), sum(m["status"] == "offline" for m in data.meters()), "offline meters KPI")
