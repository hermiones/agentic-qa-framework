"""Test oracle: expected values come from the same seed data the app was loaded with."""
import json

from .config import FIXTURES_DIR
from .errors import TestDataError


def load_fixture(name: str):
    path = FIXTURES_DIR / name
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as e:
        raise TestDataError(f"fixture file missing: {path}") from e
    except json.JSONDecodeError as e:
        raise TestDataError(f"fixture file is not valid JSON: {path}: {e}") from e


def meters() -> list[dict]:
    return load_fixture("meters.json")


def meter(meter_id: str) -> dict:
    for m in meters():
        if m["id"] == meter_id:
            return m
    raise TestDataError(f"meter {meter_id} is not in the seed data")


def total_kwh(m: dict) -> float:
    return round(sum(m["readings"]), 1)
