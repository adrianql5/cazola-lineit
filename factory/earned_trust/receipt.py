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
    cl, jd = report["classifier"], report["judge"]
    checked = [
        {"item": f"Sorted all {ch['files']} files" + (f"; {len(cl['outliers'])} of {cl['snapshots']} snapshots didn't match and went to a person" if cl["snapshots"] else ""), "by": "machine"},
        {"item": f"Checked the file and line of {jd['total']} accusations; threw out {len(jd['rejected'])}", "by": "machine"},
        {"item": f"Matched {len(tr['claims'])} claims to code and tests", "by": "machine"},
    ]
    if tr["execution"]["status"] == "PASS":
        checked.append({"item": f"Ran the {tr['execution']['passed']} tests this PR adds: all passed", "by": "machine"})
    if state.get("spotcheck"):
        s = state["spotcheck"]
        checked.append({"item": f"Opened {len(s['sample'])} random hidden files: {'all fine' if s['result'] == 'clean' else 'found a problem'}", "by": f"human:{s['by']}"})
    checked.append({"item": f"Read {rt['read']['lines_must_read']} lines in {rt['read']['files_must_read']} files",
                    "by": "human:" + ",".join(s["by"] for s in state["signatures"])})
    findings = []
    for f in report["judge"]["accepted"]:
        v = state["findings"].get(f["id"], {})
        findings.append({"id": f["id"], "citation": f"{f['file']}:{f['line_start']}", "verdict": v.get("verdict"),
                         "by": v.get("by"), "evidence": v.get("evidence")})
    residual = [f"{f['id']}: {next(x['claim'] for x in report['judge']['accepted'] if x['id'] == f['id'])}"
                for f in findings if f["verdict"] == "accepted"]
    residual += [f"No test for: {c['claim'][:120]}" for c in tr["claims"] if c["status"] == "UNVERIFIED"]
    residual += [f"Contradicted: {c['claim'][:120]}" for c in tr["claims"] if c["status"] == "CONTRADICTED"]
    if tr["execution"]["status"] != "PASS":
        residual.append("Signed without a passing test run")
    if state.get("summary_disabled"):
        residual.append("The spot-check found a problem, so every file was read")
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
    signers = ", ".join(f"{x['name']} (@{x['by']})" for x in rc["signatures"])
    when = rc["signatures"][-1]["at"][:10] if rc["signatures"] else ""
    L = [f"## Receipt · {rc['requirement']}", "",
         f"Signed by **{signers}** on {when} · commit `{rc['commit_sha'][:10]}`  ",
         f"Receipt hash `{rc['hash'][:16]}` (full hash in receipt.json)", ""]
    machine = [c["item"] for c in rc["checked"] if c["by"] == "machine"]
    people = [(c["item"], c["by"].split(":", 1)[1]) for c in rc["checked"] if c["by"].startswith("human:")]
    L += ["**Checked by the machine**"] + [f"- {x}" for x in machine] + [""]
    L += ["**Checked by people**"] + [f"- {x} (@{who})" for x, who in people] + [""]
    if rc["decisions"]:
        L += ["**Decisions**"] + [f"- {d['abstention']}: `{d['option']}`, by @{d['by']}: \"{d['reason']}\"" for d in rc["decisions"]] + [""]
    if rc["findings"]:
        L += ["**Findings**"] + [f"- {f['id']}: {f['verdict']} by @{f['by']}" + (f": \"{f['evidence']}\"" if f.get("evidence") else "")
                                 for f in rc["findings"]] + [""]
    L += ["**Not checked**"] + [f"- {c['item']}: {c['why']}" for c in rc["not_checked"]] + [""]
    L += ["**Risk the signer accepts**"] + [f"- {x}" for x in rc["residual_risk_accepted"]] + [""]
    return "\n".join(L)


def write(rc: dict, run_dir: Path) -> None:
    (run_dir / "receipt.json").write_text(json.dumps(rc, indent=1))
    (run_dir / "receipt.md").write_text(markdown(rc))
    led = Path(os.environ.get("ET_LEDGER_DIR") or FACTORY.parent / "ledger") / "receipts"
    led.mkdir(parents=True, exist_ok=True)
    (led / f"{rc['branch']}-{rc['commit_sha'][:10]}-{rc['hash'][:12]}.json").write_text(json.dumps(rc, indent=1))
