"""Central configuration. Every value can be overridden with an environment variable."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("DEMO_BASE_URL", "http://127.0.0.1:8765")
TEST_SESSION_KEY = os.environ.get("DEMO_TEST_SESSION_KEY", "local-demo-key")
AUTH_DIR = ROOT / ".auth"
REPORTS_DIR = ROOT / "reports"
ARTIFACTS_DIR = REPORTS_DIR / "artifacts"
REQUIREMENTS_FILE = ROOT / "requirements.yaml"
FIXTURES_DIR = ROOT / "demo_app" / "fixtures"
# Seeded users that sessions get captured for (role -> username)
SEEDED_USERS = {"viewer": "qa_viewer", "admin": "qa_admin"}
