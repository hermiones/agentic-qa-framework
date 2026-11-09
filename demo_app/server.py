"""Tiny smart-meter dashboard used as the system under test.

Pure Python standard library, with no dependencies. It mimics the parts of a real
utility web client that make UI automation hard:

* a login page protected by a server-side CAPTCHA (automation never solves it)
* role-based pages (viewer vs admin)
* business values that tests can verify against the seed data

It ships with ONE deliberate bug (see `online_count`) so the failure classifier
has a real product defect to find when you run the demo failures.

Test-only hook: GET /__test__/session issues a session cookie for a seeded user.
That stands in for "a human logs in once and the session is captured". Disable it
with DEMO_TEST_HOOKS=0.
"""
from __future__ import annotations

import html
import json
import os
import random
import secrets
import string
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

HERE = Path(__file__).parent
USERS = {u["username"]: u for u in json.loads((HERE / "fixtures/users.json").read_text())}
METERS = json.loads((HERE / "fixtures/meters.json").read_text())

PORT = int(os.environ.get("DEMO_PORT", "8765"))
SESSION_TTL = int(os.environ.get("DEMO_SESSION_TTL", "3600"))
TEST_HOOKS = os.environ.get("DEMO_TEST_HOOKS", "1") != "0"
TEST_SESSION_KEY = os.environ.get("DEMO_TEST_SESSION_KEY", "local-demo-key")

SESSIONS: dict[str, dict] = {}   # token -> {"user": username, "exp": epoch}
CAPTCHAS: dict[str, str] = {}    # challenge id -> answer


def total_kwh(meter: dict) -> float:
    return round(sum(meter["readings"]), 1)


def online_count() -> int:
    # DELIBERATE BUG for the demo: "maintenance" meters are counted as online.
    return sum(1 for m in METERS if m["status"] in ("online", "maintenance"))


CSS = """
body{font-family:system-ui,sans-serif;margin:0;background:#f5f7fa;color:#122033}
header{background:#0a1018;color:#e6edf3;padding:12px 24px;display:flex;gap:18px;align-items:center}
header a{color:#8cc8ff;text-decoration:none}
main{max-width:960px;margin:24px auto;padding:0 20px}
.card{background:#fff;border:1px solid #d9e0e8;border-radius:8px;padding:18px;margin-bottom:16px}
.kpis{display:flex;gap:12px}.kpi{flex:1}
.kpi b{display:block;font-size:2rem}
table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #e3e8ee;text-align:left}
.error{color:#b42318;font-weight:600}.denied{color:#b42318}
input,select,button{font:inherit;padding:8px;margin:4px 0}
"""


def layout(title: str, body: str, user: dict | None = None) -> bytes:
    nav = ""
    if user:
        nav = (
            '<a data-testid="nav-dashboard" href="/dashboard">Dashboard</a>'
            '<a data-testid="nav-meters" href="/meters">Meters</a>'
            '<a data-testid="nav-reports" href="/reports">Reports</a>'
            f'<span style="margin-left:auto" data-testid="current-user">{html.escape(user["display_name"])}</span>'
            '<a data-testid="logout" href="/logout">Log out</a>'
        )
    page = (
        f"<!doctype html><html><head><meta charset=utf-8><title>{html.escape(title)} · GridSim</title>"
        f"<style>{CSS}</style></head><body><header><b>GridSim</b>{nav}</header><main>{body}</main></body></html>"
    )
    return page.encode()


def captcha_svg(answer: str) -> bytes:
    rnd = random.Random(answer)
    parts = [
        f'<text x="{12 + i * 22}" y="{30 + rnd.randint(-6, 6)}" transform="rotate({rnd.randint(-25, 25)} {12 + i * 22} 30)" '
        f'font-size="24" font-family="monospace" fill="#333">{c}</text>'
        for i, c in enumerate(answer)
    ]
    noise = "".join(
        f'<line x1="{rnd.randint(0, 150)}" y1="{rnd.randint(0, 45)}" x2="{rnd.randint(0, 150)}" y2="{rnd.randint(0, 45)}" stroke="#999"/>'
        for _ in range(8)
    )
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="150" height="45">{noise}{"".join(parts)}</svg>'.encode()


class Handler(BaseHTTPRequestHandler):
    server_version = "GridSim/1.0"

    # ---------- helpers ----------
    def log_message(self, fmt, *args):  # keep test output quiet
        if os.environ.get("DEMO_VERBOSE"):
            super().log_message(fmt, *args)

    def send(self, status: int, body: bytes = b"", ctype: str = "text/html; charset=utf-8", headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location: str, headers: dict | None = None):
        self.send(302, b"", headers={"Location": location, **(headers or {})})

    def current_user(self) -> dict | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie.get("session")
        if not token:
            return None
        sess = SESSIONS.get(token.value)
        if not sess or sess["exp"] < time.time():
            SESSIONS.pop(token.value, None)
            return None
        return USERS.get(sess["user"])

    def new_session(self, username: str) -> str:
        token = secrets.token_urlsafe(24)
        SESSIONS[token] = {"user": username, "exp": time.time() + SESSION_TTL}
        return f"session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL}"

    def require(self, path: str, admin: bool = False, api: bool = False) -> dict | None:
        user = self.current_user()
        if not user:
            if api:
                self.send(401, b'{"error":"unauthenticated"}', "application/json")
            else:
                self.redirect(f"/login?next={quote(path)}")
            return None
        if admin and user["role"] != "admin":
            self.send(403, layout("Access denied", '<div class="card denied" data-testid="access-denied">'
                                  "Access denied: reports are available to admins only.</div>", user))
            return None
        return user

    # ---------- routes ----------
    def do_GET(self):
        url = urlparse(self.path)
        path, qs = url.path, parse_qs(url.query)

        if path == "/health":
            return self.send(200, b"ok", "text/plain")
        if path == "/":
            return self.redirect("/dashboard")
        if path == "/login":
            return self.login_page(qs.get("next", ["/dashboard"])[0])
        if path.startswith("/captcha/") and path.endswith(".svg"):
            answer = CAPTCHAS.get(path[len("/captcha/"):-4])
            return self.send(200 if answer else 404, captcha_svg(answer or "?"), "image/svg+xml")
        if path == "/logout":
            return self.redirect("/login", {"Set-Cookie": "session=; Path=/; Max-Age=0"})
        if path == "/__test__/session" and TEST_HOOKS:
            return self.test_session(qs)
        if path == "/api/whoami":
            user = self.require(path, api=True)
            if user:
                self.send(200, json.dumps({"user": user["username"], "role": user["role"]}).encode(), "application/json")
            return
        if path == "/api/meters":
            if self.require(path, api=True):
                self.send(200, json.dumps(METERS).encode(), "application/json")
            return
        if path == "/dashboard":
            return self.dashboard(path)
        if path == "/meters":
            return self.meters(path)
        if path.startswith("/meters/"):
            return self.meter_detail(path)
        if path == "/reports":
            return self.reports(path, "generate" in qs)
        if path == "/reports/export.csv":
            return self.export_csv(path)
        self.send(404, layout("Not found", '<div class="card" data-testid="not-found">Page not found</div>'))

    def do_POST(self):
        if urlparse(self.path).path != "/login":
            return self.send(405, b"method not allowed", "text/plain")
        length = int(self.headers.get("Content-Length", "0"))
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode()).items()}
        user = USERS.get(form.get("username", ""))
        expected = CAPTCHAS.pop(form.get("challenge", ""), None)
        if not expected or form.get("captcha", "").strip().upper() != expected:
            return self.login_page(form.get("next", "/dashboard"), "CAPTCHA verification failed. Please try again.")
        if not user or user["password"] != form.get("password"):
            return self.login_page(form.get("next", "/dashboard"), "Invalid username or password.")
        self.redirect(form.get("next") or "/dashboard", {"Set-Cookie": self.new_session(user["username"])})

    # ---------- pages ----------
    def login_page(self, nxt: str, error: str = ""):
        cid = secrets.token_hex(8)
        CAPTCHAS[cid] = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        err = f'<p class="error" data-testid="login-error">{html.escape(error)}</p>' if error else ""
        body = f"""<div class="card" style="max-width:380px">
<h1>Sign in</h1>{err}
<form method="post" action="/login" data-testid="login-form">
<input type="hidden" name="next" value="{html.escape(nxt)}"><input type="hidden" name="challenge" value="{cid}">
<label>Username<br><input name="username" data-testid="username" autocomplete="username"></label><br>
<label>Password<br><input name="password" type="password" data-testid="password" autocomplete="current-password"></label><br>
<img src="/captcha/{cid}.svg" alt="CAPTCHA" data-testid="captcha-image"><br>
<label>Type the characters above<br><input name="captcha" data-testid="captcha"></label><br>
<button type="submit" data-testid="sign-in">Sign in</button></form></div>"""
        self.send(200, layout("Sign in", body))

    def test_session(self, qs):
        if qs.get("key", [""])[0] != TEST_SESSION_KEY:
            return self.send(403, b'{"error":"bad test key"}', "application/json")
        username = qs.get("user", [""])[0]
        if username not in USERS:
            return self.send(404, b'{"error":"unknown seeded user"}', "application/json")
        body = json.dumps({"ok": True, "user": username, "expires_in": SESSION_TTL}).encode()
        self.send(200, body, "application/json", {"Set-Cookie": self.new_session(username)})

    def dashboard(self, path):
        user = self.require(path)
        if not user:
            return
        offline = sum(1 for m in METERS if m["status"] == "offline")
        body = f"""<h1 data-testid="welcome">Welcome, {html.escape(user["display_name"])}</h1>
<div class="kpis"><div class="card kpi">Total meters<b data-testid="kpi-total">{len(METERS)}</b></div>
<div class="card kpi">Online<b data-testid="kpi-online">{online_count()}</b></div>
<div class="card kpi">Offline<b data-testid="kpi-offline">{offline}</b></div></div>"""
        self.send(200, layout("Dashboard", body, user))

    def meters(self, path):
        user = self.require(path)
        if not user:
            return
        rows = "".join(
            f'<tr data-testid="meter-row" data-status="{m["status"]}"><td><a href="/meters/{m["id"]}" data-testid="meter-link">{m["id"]}</a></td>'
            f'<td>{html.escape(m["location"])}</td><td data-testid="meter-status">{m["status"]}</td><td>{total_kwh(m)} kWh</td></tr>'
            for m in METERS
        )
        body = f"""<h1>Meters</h1><div class="card">
<input data-testid="meter-search" placeholder="Search by id or location">
<select data-testid="status-filter"><option value="">All statuses</option><option>online</option><option>offline</option><option>maintenance</option></select>
<p data-testid="meter-count">Showing {len(METERS)} meters</p>
<table><thead><tr><th>Meter</th><th>Location</th><th>Status</th><th>Total</th></tr></thead><tbody>{rows}</tbody></table></div>
<script>
const q=document.querySelector('[data-testid=meter-search]'),s=document.querySelector('[data-testid=status-filter]'),c=document.querySelector('[data-testid=meter-count]');
function f(){{let n=0;document.querySelectorAll('[data-testid=meter-row]').forEach(r=>{{const ok=r.textContent.toLowerCase().includes(q.value.toLowerCase())&&(!s.value||r.dataset.status===s.value);r.hidden=!ok;if(ok)n++}});c.textContent='Showing '+n+' meters'}}
q.addEventListener('input',f);s.addEventListener('change',f);
</script>"""
        self.send(200, layout("Meters", body, user))

    def meter_detail(self, path):
        user = self.require(path)
        if not user:
            return
        meter = next((m for m in METERS if m["id"] == path.rsplit("/", 1)[-1]), None)
        if not meter:
            return self.send(404, layout("Not found", '<div class="card" data-testid="not-found">Meter not found</div>', user))
        rows = "".join(f'<tr data-testid="reading-row"><td>#{i + 1}</td><td>{r} kWh</td></tr>' for i, r in enumerate(meter["readings"]))
        body = f"""<h1 data-testid="meter-id">{meter["id"]}</h1><div class="card">
<p>Location: {html.escape(meter["location"])} · Status: <b data-testid="meter-status">{meter["status"]}</b></p>
<table><tbody>{rows}</tbody></table><p>Total: <b data-testid="total-kwh">{total_kwh(meter)} kWh</b></p></div>"""
        self.send(200, layout(meter["id"], body, user))

    def reports(self, path, generate: bool):
        user = self.require(path, admin=True)
        if not user:
            return
        summary = ""
        if generate:
            total = round(sum(total_kwh(m) for m in METERS), 1)
            summary = f'<p data-testid="report-total">Total consumption: {total} kWh</p>'
        body = f"""<h1>Reports</h1><div class="card">
<a href="/reports?generate=1" data-testid="generate-report">Generate consumption report</a>{summary}
<p><a id="export-csv" data-testid="export-csv" href="/reports/export.csv">Export CSV</a></p></div>"""
        self.send(200, layout("Reports", body, user))

    def export_csv(self, path):
        if not self.require(path, admin=True):
            return
        lines = ["meter_id,location,status,total_kwh"] + [f'{m["id"]},{m["location"]},{m["status"]},{total_kwh(m)}' for m in METERS]
        self.send(200, ("\n".join(lines) + "\n").encode(), "text/csv", {"Content-Disposition": "attachment; filename=consumption.csv"})


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"GridSim demo app on http://127.0.0.1:{PORT} (test hooks {'on' if TEST_HOOKS else 'off'}, session TTL {SESSION_TTL}s)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
