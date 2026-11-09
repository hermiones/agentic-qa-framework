"""CI guard: after running the intentional demo failures, the classifier must have put
each one in the expected bucket. This tests the triage logic itself."""
import json
import sys
from pathlib import Path

EXPECTED = {
    "test_demo_product_defect_online_kpi": "product_defect",
    "test_demo_ui_change_export_button_renamed": "ui_change",
    "test_demo_environment_dependency_down": "environment",
}
data = json.loads(Path("reports/classification.json").read_text())
got = {f["nodeid"].split("::")[-1].split("[")[0]: f["category"] for f in data["failures"]}
ok = True
for test, cat in EXPECTED.items():
    actual = got.get(test)
    print(f"{'OK  ' if actual == cat else 'FAIL'} {test}: expected {cat}, got {actual}")
    ok &= actual == cat
defects = Path("reports/defect_log.md").read_text().count("## DEF-")
print(f"{'OK  ' if defects == 1 else 'FAIL'} defect log contains {defects} entr(y/ies) (expected 1: only the product defect)")
sys.exit(0 if ok and defects == 1 else 1)
