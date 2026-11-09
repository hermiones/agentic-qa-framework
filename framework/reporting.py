"""Writes the run's outputs:

reports/defect_log.md      only product defects, with evidence (the "real findings")
reports/triage_summary.md  every failure, with its category, rule and owner
reports/traceability.md    requirement -> tests -> status, including uncovered requirements
reports/classification.json  machine-readable version of the above
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .classifier import ENVIRONMENT, PRODUCT_DEFECT, TEST_DATA, TEST_ISSUE, UI_CHANGE

OWNER = {
    PRODUCT_DEFECT: "Dev team (log as defect)",
    UI_CHANGE: "QA: update locator / page object",
    ENVIRONMENT: "DevOps: environment health",
    TEST_DATA: "QA: fix fixtures / seed data",
    TEST_ISSUE: "QA: fix test code",
}


def _rel(p: str | None, root: Path) -> str:
    if not p:
        return "-"
    try:
        return str(Path(p).resolve().relative_to(root))
    except ValueError:
        return p


def write_reports(reports_dir: Path, root: Path, failures: list[dict], outcomes: dict, req_map: dict, requirements: dict):
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")

    # ---- defect log: product defects only ----
    defects = [f for f in failures if f["category"] == PRODUCT_DEFECT]
    lines = [f"# Defect log\n\nGenerated {stamp}. Only failures classified as **product_defect** are listed here.\n"]
    if not defects:
        lines.append("_No product defects in this run._\n")
    for i, d in enumerate(defects, 1):
        lines += [
            f"## DEF-{i:03d}: {d['reason']}",
            f"- **Test:** `{d['nodeid']}`",
            f"- **Browser:** {d.get('browser') or '-'}",
            f"- **Requirement(s):** {', '.join(d['requirements']) or '-'}",
            f"- **Rule:** {d['rule']}",
            f"- **Screenshot:** {_rel(d.get('screenshot'), root)}",
            f"- **Trace:** {_rel(d.get('trace'), root)}  (open with `playwright show-trace <file>`)",
            "",
        ]
    (reports_dir / "defect_log.md").write_text("\n".join(lines))

    # ---- triage summary: everything ----
    counts = {}
    for f in failures:
        counts[f["category"]] = counts.get(f["category"], 0) + 1
    t = [f"# Triage summary\n\nGenerated {stamp}. {len(failures)} failure(s) classified.\n",
         "| Category | Count | Owner |", "|---|---|---|"]
    for cat in (PRODUCT_DEFECT, UI_CHANGE, ENVIRONMENT, TEST_DATA, TEST_ISSUE):
        t.append(f"| {cat} | {counts.get(cat, 0)} | {OWNER[cat]} |")
    t += ["", "| Test | Browser | Category | Rule | Reason |", "|---|---|---|---|---|"]
    for f in failures:
        t.append(f"| `{f['nodeid']}` | {f.get('browser') or '-'} | **{f['category']}** | {f['rule']} | {f['reason'].replace('|', '/')} |")
    (reports_dir / "triage_summary.md").write_text("\n".join(t) + "\n")

    # ---- traceability ----
    tr = [f"# Requirement traceability\n\nGenerated {stamp}.\n", "| Requirement | Title | Tests | Status |", "|---|---|---|---|"]
    covered = 0
    for rid, title in requirements.items():
        tests = req_map.get(rid, [])
        if not tests:
            status = "⚠️ not covered"
        else:
            covered += 1
            res = [outcomes.get(n, "not run") for n in tests]
            if "failed" in res:
                status = "❌ failing"
            elif all(r == "passed" for r in res):
                status = "✅ passing"
            elif "passed" in res:
                status = "✅ passing (some skipped)"
            else:
                status = "⏭️ skipped"
        names = "<br>".join(f"`{n.split('::')[-1]}`" for n in tests) or "-"
        tr.append(f"| {rid} | {title} | {names} | {status} |")
    unknown = sorted(set(req_map) - set(requirements))
    tr.append(f"\n**Coverage:** {covered}/{len(requirements)} requirements have at least one test.")
    if unknown:
        tr.append(f"\n**Tagged but not in requirements.yaml:** {', '.join(unknown)}")
    (reports_dir / "traceability.md").write_text("\n".join(tr) + "\n")

    (reports_dir / "classification.json").write_text(json.dumps({"generated": stamp, "failures": failures, "outcomes": outcomes}, indent=2))
