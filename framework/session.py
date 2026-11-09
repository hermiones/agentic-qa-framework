"""Session capture & replay.

The real app's login sits behind a server-side CAPTCHA, which automation must not
(and in practice cannot) solve. So:

1. capture: get an authenticated session ONCE (here via a seeded test-only endpoint,
   standing in for "a human signs in once") and save Playwright storage state to
   .auth/<role>.json
2. replay: every test gets a brand-new, isolated browser context loaded with that
   storage state, so there are no logins in tests, no shared state and no CAPTCHA
3. validate: before replaying, check the session is still alive. If it expired,
   the test is SKIPPED with a clear message instead of failing, so expired auth
   never shows up as a false product failure.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .config import AUTH_DIR, SEEDED_USERS, TEST_SESSION_KEY
from .errors import EnvironmentUnavailable


class SessionExpired(Exception):
    pass


def state_path(role: str) -> Path:
    return AUTH_DIR / f"{role}.json"


def capture(playwright, base_url: str, role: str) -> Path:
    """Capture a fresh session for a seeded role and persist it as storage state."""
    AUTH_DIR.mkdir(exist_ok=True)
    ctx = playwright.request.new_context(base_url=base_url)
    try:
        try:
            resp = ctx.get(f"/__test__/session?user={SEEDED_USERS[role]}&key={TEST_SESSION_KEY}")
        except Exception as e:  # connection refused etc.
            raise EnvironmentUnavailable(f"cannot reach {base_url} to capture a session: {e}") from e
        if resp.status >= 500:
            raise EnvironmentUnavailable(f"session endpoint answered HTTP {resp.status}")
        if not resp.ok:
            raise RuntimeError(f"session capture refused (HTTP {resp.status}): {resp.text()}")
        path = state_path(role)
        ctx.storage_state(path=str(path))
        meta = {"role": role, "captured_at": time.time(), "expires_in": resp.json().get("expires_in")}
        path.with_suffix(".meta.json").write_text(json.dumps(meta))
        return path
    finally:
        ctx.dispose()


def is_valid(playwright, base_url: str, path: Path) -> bool:
    """True if the stored session is still accepted by the server."""
    if not path.exists():
        return False
    ctx = playwright.request.new_context(base_url=base_url, storage_state=str(path))
    try:
        try:
            resp = ctx.get("/api/whoami")
        except Exception as e:
            raise EnvironmentUnavailable(f"cannot reach {base_url} to validate the session: {e}") from e
        if resp.status >= 500:
            raise EnvironmentUnavailable(f"whoami answered HTTP {resp.status}")
        return resp.status == 200
    finally:
        ctx.dispose()


def get_state(playwright, base_url: str, role: str, recapture: bool = False) -> Path:
    """Reuse a captured session if it is still valid, otherwise capture once.

    Raises SessionExpired if even a fresh capture is not accepted (e.g. the TTL is
    shorter than the time it takes to start the tests). Callers turn that into a skip.
    """
    path = state_path(role)
    if not recapture and is_valid(playwright, base_url, path):
        return path
    path = capture(playwright, base_url, role)
    if not is_valid(playwright, base_url, path):
        raise SessionExpired(
            f"captured '{role}' session was rejected immediately; it has probably expired. "
            "Re-capture it (pytest --recapture-session) or raise DEMO_SESSION_TTL"
        )
    return path
