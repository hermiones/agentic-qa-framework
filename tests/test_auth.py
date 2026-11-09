"""Authentication: the CAPTCHA blocks automation, so tests use session replay instead."""
import re

import pytest
from playwright.sync_api import expect

from framework.pages import DashboardPage, LoginPage


@pytest.mark.req("REQ-001")
def test_login_is_blocked_without_captcha(anon_page):
    """Valid credentials are not enough: the server-side CAPTCHA must pass too."""
    login = LoginPage(anon_page).open()
    expect(login.captcha_image).to_be_visible()
    login.submit("qa_viewer", "demo-viewer-pass", captcha="WRONG1")
    expect(login.error).to_have_text(re.compile("CAPTCHA verification failed"))
    expect(anon_page).to_have_url(re.compile(r"/login"))


@pytest.mark.req("REQ-002")
def test_protected_pages_redirect_to_login(anon_page):
    anon_page.goto("/meters")
    expect(anon_page).to_have_url(re.compile(r"/login\?next=%2Fmeters|/login\?next=/meters"))


@pytest.mark.req("REQ-003")
def test_replayed_session_lands_on_dashboard(viewer_page):
    """No login, no CAPTCHA: the captured session is replayed into a fresh context."""
    dash = DashboardPage(viewer_page).open()
    expect(dash.welcome).to_have_text("Welcome, QA Viewer")
    expect(dash.current_user).to_have_text("QA Viewer")
