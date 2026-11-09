"""Automatic failure classification.

Every failed test is put into exactly one bucket, using explicit, ordered rules.
Only `product_defect` goes to the defect log. Everything else goes to a triage
summary for the owning team (QA, DevOps, frontend), so the defect register only
holds real findings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PRODUCT_DEFECT = "product_defect"
UI_CHANGE = "ui_change"
ENVIRONMENT = "environment"
TEST_DATA = "test_data"
TEST_ISSUE = "test_issue"

# (rule id, category, human-readable rule). Kept as data so the README table and
# the code can't drift apart.
RULES = [
    ("R1", TEST_DATA, "TestDataError, or a missing/invalid fixture file during setup"),
    ("R2", ENVIRONMENT, "Connection refused / DNS / HTTP 5xx / EnvironmentUnavailable"),
    ("R3", PRODUCT_DEFECT, "BusinessRuleViolation: a business value (count, total, status) is wrong"),
    ("R4", UI_CHANGE, "Locator timed out or element not found: the UI changed under the test"),
    ("R5", PRODUCT_DEFECT, "Any other assertion on what the product shows (Playwright expect / assert)"),
    ("R6", TEST_ISSUE, "Anything else (TypeError, NameError, bad test code)"),
]

_ENV_PATTERNS = re.compile(
    r"ECONNREFUSED|ERR_CONNECTION_REFUSED|Connection refused|ConnectionRefusedError|"
    r"ERR_NAME_NOT_RESOLVED|getaddrinfo|EnvironmentUnavailable|HTTP 5\d\d|status(?:\s*code)?\s*[:=]?\s*5\d\d",
    re.I,
)
# A locator action that timed out while waiting for an element...
_WAITING = re.compile(r"waiting for (?:locator|selector|get_by)", re.I)
# ...or an assertion whose element was never found (as opposed to found-but-wrong-value)
_NOT_FOUND = re.compile(r"element\(s\) not found|strict mode violation|resolved to 0 elements", re.I)


@dataclass
class Classification:
    category: str
    rule: str
    reason: str


def _chain(exc):
    """The exception plus its causes, so wrapped errors are classified by root cause."""
    seen = []
    while exc is not None and exc not in seen:
        seen.append(exc)
        exc = exc.__cause__ or exc.__context__
    return seen


def classify(exc: BaseException, when: str) -> Classification:
    chain = _chain(exc)
    names = {type(e).__name__ for e in chain}
    text = " | ".join(f"{type(e).__name__}: {e}" for e in chain)
    first_line = str(exc).strip().splitlines()[0][:220] if str(exc).strip() else type(exc).__name__

    if "TestDataError" in names or (when == "setup" and names & {"FileNotFoundError", "JSONDecodeError", "YAMLError"}):
        return Classification(TEST_DATA, "R1", first_line)
    if "EnvironmentUnavailable" in names or "ConnectionRefusedError" in names or _ENV_PATTERNS.search(text):
        return Classification(ENVIRONMENT, "R2", first_line)
    if "BusinessRuleViolation" in names:
        return Classification(PRODUCT_DEFECT, "R3", first_line)
    if ("TimeoutError" in names and _WAITING.search(text)) or _NOT_FOUND.search(text):
        return Classification(UI_CHANGE, "R4", first_line)
    if isinstance(exc, AssertionError):
        return Classification(PRODUCT_DEFECT, "R5", first_line)
    return Classification(TEST_ISSUE, "R6", first_line)
