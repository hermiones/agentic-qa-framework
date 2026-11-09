"""Assertion helpers that tag failures with intent, so the classifier can triage them."""
from .errors import BusinessRuleViolation


def expect_business(actual, expected, what: str, tolerance: float = 0.0):
    """Assert a business value (counts, totals, money...). A mismatch is a product defect."""
    ok = abs(float(actual) - float(expected)) <= tolerance if isinstance(expected, (int, float)) else actual == expected
    if not ok:
        raise BusinessRuleViolation(f"[business] {what}: expected {expected!r}, got {actual!r}")
