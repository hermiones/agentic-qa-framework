"""Framework wiring: session-replay fixtures, artifact capture, failure classification
and requirement traceability. Tests stay small; everything else lives here."""
from __future__ import annotations

import os
import re

import pytest
import yaml

from framework import session as sess
from framework.classifier import classify
from framework.config import ARTIFACTS_DIR, REPORTS_DIR, REQUIREMENTS_FILE, ROOT
from framework.reporting import write_reports

FAILURES = pytest.StashKey[list]()
ENTRIES = pytest.StashKey[dict]()
OUTCOMES = pytest.StashKey[dict]()
REQ_MAP = pytest.StashKey[dict]()


# ---------------------------------------------------------------- options & setup
def pytest_addoption(parser):
    parser.addoption("--recapture-session", action="store_true", help="ignore cached .auth sessions and capture fresh ones")


def pytest_configure(config):
    config.addinivalue_line("markers", "req(*ids): requirement ids this test verifies (traceability)")
    config.addinivalue_line("markers", "demo_failure: intentionally failing test, runs only with DEMO_FAILURES=1")
    config.stash[FAILURES] = []
    config.stash[ENTRIES] = {}
    config.stash[OUTCOMES] = {}
    config.stash[REQ_MAP] = {}


def pytest_collection_modifyitems(config, items):
    run_demo = os.environ.get("DEMO_FAILURES") == "1"
    for item in items:
        if item.get_closest_marker("demo_failure") and not run_demo:
            item.add_marker(pytest.mark.skip(reason="intentional demo failure; run with DEMO_FAILURES=1 to see the classifier"))
        for m in item.iter_markers("req"):
            for rid in m.args:
                config.stash[REQ_MAP].setdefault(rid, []).append(item.nodeid)


# ---------------------------------------------------------------- classification hook
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)

    outcomes = item.config.stash[OUTCOMES]
    if rep.failed:
        outcomes[item.nodeid] = "failed"
    elif rep.skipped and outcomes.get(item.nodeid) != "failed":
        outcomes[item.nodeid] = "skipped"
    elif rep.when == "call" and rep.passed and item.nodeid not in outcomes:
        outcomes[item.nodeid] = "passed"

    if rep.failed and call.excinfo is not None and item.nodeid not in item.config.stash[ENTRIES]:
        c = classify(call.excinfo.value, rep.when)
        entry = {
            "nodeid": item.nodeid,
            "when": rep.when,
            "browser": item.funcargs.get("browser_name") if hasattr(item, "funcargs") else None,
            "category": c.category,
            "rule": c.rule,
            "reason": c.reason,
            "requirements": [rid for m in item.iter_markers("req") for rid in m.args],
        }
        item.config.stash[FAILURES].append(entry)
        item.config.stash[ENTRIES][item.nodeid] = entry
        rep.sections.append(("failure classification", f"{c.category} ({c.rule}): {c.reason}"))


def pytest_terminal_summary(terminalreporter, config):
    failures = config.stash[FAILURES]
    if failures:
        terminalreporter.section("failure classification")
        for f in failures:
            terminalreporter.write_line(f"{f['category']:<15} {f['rule']}  {f['nodeid']}  ->  {f['reason'][:120]}")
    terminalreporter.write_line(f"reports written to {REPORTS_DIR.relative_to(ROOT)}/ (defect_log.md, triage_summary.md, traceability.md)")


def pytest_sessionfinish(session):
    cfg = session.config
    if not hasattr(cfg, "stash") or FAILURES not in cfg.stash:
        return
    write_reports(REPORTS_DIR, ROOT, cfg.stash[FAILURES], cfg.stash[OUTCOMES], cfg.stash[REQ_MAP], load_requirements())


# ---------------------------------------------------------------- fixtures
def load_requirements() -> dict:
    data = yaml.safe_load(REQUIREMENTS_FILE.read_text()) or {}
    return {r["id"]: r["title"] for r in data.get("requirements", [])}


class _Sessions:
    """Captures each role's session at most once per run; caches the outcome."""

    def __init__(self, playwright, base_url, recapture):
        self.pw, self.base_url, self.recapture, self.cache = playwright, base_url, recapture, {}

    def get(self, role: str):
        if role not in self.cache:
            try:
                self.cache[role] = sess.get_state(self.pw, self.base_url, role, self.recapture)
            except sess.SessionExpired as e:
                self.cache[role] = e
        result = self.cache[role]
        if isinstance(result, Exception):
            pytest.skip(f"session for '{role}' is not valid: {result}. Skipping instead of reporting a false auth failure.")
        return str(result)


@pytest.fixture(scope="session")
def sessions(playwright, base_url, pytestconfig):
    return _Sessions(playwright, base_url, pytestconfig.getoption("--recapture-session"))


def _safe(nodeid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", nodeid)[-120:]


def _isolated_page(browser, base_url, request, storage_state=None):
    """A fresh context per test (isolation), with tracing on; artifacts kept only on failure."""
    context = browser.new_context(base_url=base_url, storage_state=storage_state)
    context.set_default_timeout(int(os.environ.get("DEMO_TIMEOUT_MS", "5000")))
    context.tracing.start(screenshots=True, snapshots=True)
    page = context.new_page()
    yield page
    failed = any(getattr(request.node, f"rep_{w}", None) and getattr(request.node, f"rep_{w}").failed for w in ("setup", "call"))
    if failed:
        out = ARTIFACTS_DIR / _safe(request.node.nodeid)
        out.mkdir(parents=True, exist_ok=True)
        shot, trace = out / "screenshot.png", out / "trace.zip"
        try:
            page.screenshot(path=str(shot), full_page=True)
        except Exception:
            shot = None
        context.tracing.stop(path=str(trace))
        entry = request.config.stash[ENTRIES].get(request.node.nodeid)
        if entry is not None:
            entry["screenshot"] = str(shot) if shot else None
            entry["trace"] = str(trace)
    else:
        context.tracing.stop()
    context.close()


@pytest.fixture
def anon_page(browser, base_url, request):
    """A logged-out page (for login / redirect tests)."""
    yield from _isolated_page(browser, base_url, request)


@pytest.fixture
def viewer_page(browser, base_url, request, sessions):
    """A page with the captured viewer session replayed into a fresh context."""
    yield from _isolated_page(browser, base_url, request, sessions.get("viewer"))


@pytest.fixture
def admin_page(browser, base_url, request, sessions):
    """A page with the captured admin session replayed into a fresh context."""
    yield from _isolated_page(browser, base_url, request, sessions.get("admin"))


@pytest.fixture
def admin_api(playwright, base_url, sessions):
    """API client carrying the admin session (for downloads / backend checks)."""
    ctx = playwright.request.new_context(base_url=base_url, storage_state=sessions.get("admin"))
    yield ctx
    ctx.dispose()
