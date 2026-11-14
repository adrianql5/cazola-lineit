"""The Accountability Receipt: what was checked and by whom (machine or a
named human), what was NOT checked and why, the decisions the AI left to a
person, and the residual risk that person accepts.

hash = sha256(brief + diff_sha + decisions). The receipt is published in the
Check Run output (immutable per run) and kept in ledger/receipts/. The PR
comment holding the brief can be edited; the check run and the ledger are the
parts that cannot.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import brief as brief_mod
from .sources import FACTORY


def build(report: dict, state: dict) -> dict:
    ch, rt, tr = report["change"], report["router"], report["tracer"]
    brief_text = brief_mod.render(report)
    decisions = [{"abstention": k, **v} for k, v in sorted(state["decisions"].items())]
    checked = [
        {"item": f"Classification of {ch['files']} files ({report['classifier']['engine']})", "by": "machine"},
        {"item": f"Pattern check over {report['classifier']['snapshots']} snapshots: "
                 f"{len(report['classifier']['outliers'])} outlier(s) routed to a human", "by": "machine"},
        {"item": f"Citations of {report['judge']['total']} accusations ({len(report['judge']['rejected'])} rejected)", "by": "machine (judge)"},
        {"item": f"{len(tr['claims'])} claims traced to diff lines and tests", "by": "machine"},
    ]
    if state.get("spotcheck"):
        s = state["spotcheck"]
        checked.append({"item": f"Spot-check of {len(s['sample'])} hidden files: {s['result']}", "by": f"human:{s['by']}"})
    checked.append({"item": f"Read {rt['read']['lines_must_read']} lines in {rt['read']['files_must_read']} files ({rt['tier']})",
                    "by": "human:" + ",".join(s["by"] for s in state["signatures"])})
    findings = []
    for f in report["judge"]["accepted"]:
        v = state["findings"].get(f["id"], {})
        findings.append({"id": f["id"], "citation": f"{f['file']}:{f['line_start']}", "verdict": v.get("verdict"),
                         "by": v.get("by"), "evidence": v.get("evidence")})
    residual = [f"{f['id']} accepted as a known issue: {next(x['claim'] for x in report['judge']['accepted'] if x['id'] == f['id'])[:160]}"
                for f in findings if f["verdict"] == "accepted"]
    residual += [f"{c['id']} {c['status']}: {c['claim'][:120]}" for c in tr["claims"] if c["status"] in ("UNVERIFIED", "CONTRADICTED")]
    if tr["execution"]["status"] != "PASS":
        residual.append(f"Tests {tr['execution']['status']}: the change is signed without a test run")
    if state.get("summary_disabled"):
        residual.append("Classifier escaped on this PR: summary mode was disabled and every file was read")
    h = hashlib.sha256((brief_text + ch["diff_sha"] + json.dumps(decisions, sort_keys=True)).encode()).hexdigest()
    return {
        "receipt_version": 1,
        "repository": "MessagePack-CSharp (junction26 mirror)",
        "branch": ch["branch"],
        "requirement": f"#{ch['issue']} {ch['issue_title']}",
        "requirement_source": tr["requirements_source"],
        "commit_sha": ch["sha"],
        "diff_sha256": ch["diff_sha"],
        "brief_sha256": hashlib.sha256(brief_text.encode()).hexdigest(),
        "tier": rt["tier"],
        "policy": {"source": rt["policy"], "rules_sha256": report["provenance"].get("policy_sha")},
        "owner": state["signatures"][0]["by"] if state["signatures"] else None,
        "signatures": state["signatures"],
        "checked": checked,
        "not_checked": report["not_checked"],
        "decisions": decisions,
        "findings": findings,
        "residual_risk_accepted": residual,
        "events": state["events"],
        "brief_published_at": state["published_at"],
        "hash": h,
    }


def markdown(rc: dict) -> str:
    L = [f"# Accountability Receipt · {rc['requirement']}", "",
         f"- Commit `{rc['commit_sha']}` on `{rc['branch']}` · tier **{rc['tier']}** · policy: {rc['policy']['source']}",
         "- Signed by: " + ", ".join(f"{s['name']} (@{s['by']}, {s['at']})" for s in rc["signatures"]),
         f"- Receipt hash: `{rc['hash']}`", "", "## Checked", ""]
    L += [f"- {c['item']} — **{c['by']}**" for c in rc["checked"]]
    L += ["", "## Not checked", ""] + [f"- {c['item']} — {c['why']}" for c in rc["not_checked"]]
    L += ["", "## Decisions the AI left to a human", ""]
    L += [f"- **{d['abstention']}** ({d['kind']}): `{d['option']}` by @{d['by']} — \"{d['reason']}\"" for d in rc["decisions"]] or ["- none"]
    L += ["", "## Findings", ""]
    L += [f"- {f['id']} `{f['citation']}`: **{f['verdict']}** by @{f['by']}" + (f" — {f['evidence']}" if f.get("evidence") else "")
          for f in rc["findings"]] or ["- none"]
    L += ["", "## Residual risk accepted", ""] + [f"- {x}" for x in rc["residual_risk_accepted"]]
    L += ["", "*The PR comment can be edited; this receipt's hash is also in the check run output and in ledger/receipts/.*"]
    return "\n".join(L) + "\n"


def write(rc: dict, run_dir: Path) -> None:
    (run_dir / "receipt.json").write_text(json.dumps(rc, indent=1))
    (run_dir / "receipt.md").write_text(markdown(rc))
    led = Path(os.environ.get("ET_LEDGER_DIR") or FACTORY.parent / "ledger") / "receipts"
    led.mkdir(parents=True, exist_ok=True)
    (led / f"{rc['branch']}-{rc['commit_sha'][:10]}-{rc['hash'][:12]}.json").write_text(json.dumps(rc, indent=1))
