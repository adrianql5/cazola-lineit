"""The replay benchmark. Writes bench/report.json, which the dashboard reads.

Every number in it says where it comes from:
  replay                 the four real branches, re-run offline
  seeded                 defects we injected on purpose (bench/mutate.py)
  upstream git history   the trust ledger
  labels                 findings labelled real / false positive by a person (bench/labels.json)
  session                /commands recorded in runs/*/state.json, live or simulated (each says which)
"""

from __future__ import annotations

import copy
import json
import tempfile
import time
from pathlib import Path

from sancho import judge, ledger, pipeline, sources
from sancho.sources import FACTORY

from . import mutate

ROOT = FACTORY.parent
OUT = FACTORY / "bench" / "report.json"


def review(change, content_check: bool = True) -> dict:
    from sancho import classifier
    orig = classifier.run
    if not content_check:
        classifier.run = lambda c, content_check=True: orig(c, content_check=False)
    try:
        with tempfile.TemporaryDirectory() as d:
            return pipeline.review(change, use_llm=False, run_dir=Path(d), write=False)
    finally:
        classifier.run = orig


def outcome(m: mutate.Mutant, r: dict, base: dict) -> dict:
    files = {f["path"]: f for f in r["classifier"]["files"]}
    base_files = {f["path"]: f for f in base["classifier"]["files"]}
    by = []
    near = lambda n: m.line is None or n is None or abs(n - m.line) <= 10
    if any(f["file"] == m.file and near(f["line_start"]) for f in r["judge"]["accepted"]):
        by.append("finding")
    if any(o["path"] == m.file for o in r["classifier"]["outliers"]):
        by.append("outlier")
    if any(t["file"] == m.file and near(t["line"]) for t in r["classifier"]["triggers"]):
        by.append("T2 trigger")
    if any(a["cite"].startswith(m.file + ":") and near(int(a["cite"].rsplit(":", 1)[1])) for a in r["abstentions"]):
        by.append("abstention")
    was = base_files.get(m.file, {}).get("category")
    if was == "mechanical" and files.get(m.file, {}).get("category") != "mechanical":
        by.append("classifier")
    new_unverified = ({c["id"] for c in r["tracer"]["claims"] if c["status"] == "UNVERIFIED"}
                      - {c["id"] for c in base["tracer"]["claims"] if c["status"] == "UNVERIFIED"})
    if new_unverified:
        by.append(f"tracer ({', '.join(sorted(new_unverified))} now UNVERIFIED)")
    if by:
        result = "FLAGGED"
    elif m.file in r["router"]["must_read"]:
        result = "ROUTED"
    elif m.file in r["sampler"].get("sample", []):
        result = "SAMPLED"
    else:
        result = "ESCAPED"
    return {"id": m.id, "branch": m.branch, "what": m.what, "file": m.file, "line": m.line, "expected": m.expect,
            "result": result, "caught_by": by, "tier": r["router"]["tier"], "base_tier": base["router"]["tier"]}


def judge_seeds(bases: dict[str, dict]) -> dict:
    """Corrupt the citations of real, accepted findings; the judge must reject every corruption."""
    rows = []
    for br, r in bases.items():
        files = sources.load(br).files
        for f in r["judge"]["accepted"]:
            orig = {k: f[k] for k in ("id", "claim", "file", "line_start", "line_end", "symbol", "source")}
            cases = [
                ("control: the real citation", orig, "ACCEPTED"),
                ("line shifted by +1000", {**orig, "line_start": orig["line_start"] + 1000, "line_end": orig["line_end"] + 1000}, "REJECTED"),
                ("symbol that is not in the code", {**orig, "symbol": "ThreadStaticUtf8Buffer"}, "REJECTED"),
                ("file not in the diff", {**orig, "file": "src/MessagePack/MessagePackReader.cs"}, "REJECTED"),
                ("no citation at all", {**orig, "file": None, "line_start": None, "line_end": None}, "REJECTED"),
            ]
            for name, acc, want in cases:
                v = judge.verdict(copy.deepcopy(acc), files)
                rows.append({"branch": br, "finding": f["id"], "case": name, "expected": want, "got": v["verdict"],
                             "ok": v["verdict"] == want})
    corrupt = [x for x in rows if x["expected"] == "REJECTED"]
    control = [x for x in rows if x["expected"] == "ACCEPTED"]
    return {"source": "seeded (citation corruptions of real findings)",
            "corruptions": len(corrupt), "rejected": sum(x["ok"] for x in corrupt),
            "controls": len(control), "accepted": sum(x["ok"] for x in control), "rows": rows}


def precision(bases: dict[str, dict]) -> dict:
    labels = json.loads((FACTORY / "bench" / "labels.json").read_text())
    rows, real, fp, unl = [], 0, 0, 0
    for br, r in bases.items():
        for f in r["judge"]["accepted"]:
            lab = labels["labels"].get(br, {}).get(f["id"])
            if lab is None:
                unl += 1
            elif lab["label"] == "real":
                real += 1
            else:
                fp += 1
            rows.append({"branch": br, "finding": f["id"], "label": lab["label"] if lab else "unlabelled",
                         "note": lab["note"] if lab else ""})
    return {"source": f"labels ({labels['labelled_by']})", "real": real, "false_positive": fp, "unlabelled": unl,
            "precision": round(real / (real + fp), 3) if real + fp else None, "rows": rows}


def sessions() -> dict:
    rows = []
    for st in sorted((ROOT / "runs").glob("*/state.json")):
        s = json.loads(st.read_text())
        ev = s["events"]
        acc = sum(1 for e in ev if e["command"].startswith("/accept"))
        ref = sum(1 for e in ev if e["command"].startswith("/refute"))
        simulated = any(e["simulated"] for e in ev)
        signed = next((e["at"] for e in ev if e["command"].startswith("/sign")), None)
        minutes = None
        if signed and not simulated:
            t = lambda x: time.mktime(time.strptime(x, "%Y-%m-%dT%H:%M:%SZ"))
            minutes = round((t(signed) - t(s["published_at"])) / 60, 1)
        rows.append({"branch": st.parent.name, "simulated": simulated, "accepted": acc, "refuted": ref,
                     "signed": bool(s.get("signed_complete")), "minutes_brief_to_sign": minutes,
                     "spotcheck": (s.get("spotcheck") or {}).get("result")})
    return {"source": "session (runs/*/state.json; simulated sessions are scripted and have no timing)", "rows": rows}


def main() -> dict:
    t0 = time.time()
    trust = ledger.trust_table()
    bases = {br: review(sources.load(br)) for br in sources.branches()}
    real = []
    for br, r in bases.items():
        rd = r["router"]["read"]
        real.append({"branch": br, "tier": r["router"]["tier"], "files": rd["files_total"],
                     "files_must_read": rd["files_must_read"], "lines": rd["lines_total"],
                     "lines_must_read": rd["lines_must_read"],
                     "share_lines_to_human": round(rd["lines_must_read"] / rd["lines_total"], 3),
                     "share_files_to_human": round(rd["files_must_read"] / rd["files_total"], 3),
                     "findings": len(r["judge"]["accepted"]), "rejected": len(r["judge"]["rejected"]),
                     "accusations": r["judge"]["total"], "abstentions": len(r["abstentions"]),
                     "claims": r["tracer"]["counts"], "llm": r["prosecutor"]["llm"]["status"]})

    seeded = [outcome(m, review(m.change), bases[m.branch]) for m in mutate.mutants()]
    caught = [x for x in seeded if x["result"] in ("FLAGGED", "ROUTED", "SAMPLED")]
    flagged = [x for x in seeded if x["result"] == "FLAGGED"]

    sweeps = {}
    for cc in (False, True):
        ms = mutate.shape_preserving(cc)
        rows = [outcome(m, review(m.change, content_check=cc), bases[m.branch]) for m in ms]
        sweeps["with_content_check" if cc else "shape_only"] = {
            "mutants": len(rows),
            "flagged": sum(r["result"] == "FLAGGED" for r in rows),
            "sampled": sum(r["result"] == "SAMPLED" for r in rows),
            "escaped": sum(r["result"] == "ESCAPED" for r in rows),
        }
    for v in sweeps.values():
        v["escape_rate"] = round(v["escaped"] / v["mutants"], 3)

    # guardrail: a module that let a seeded defect escape loses a level of trust
    demote = {"EARNED": "PROBATION", "PROBATION": "REVOKED", "REVOKED": "REVOKED"}
    actions = []
    escaped = [x for x in seeded if x["result"] == "ESCAPED"]
    if sweeps["with_content_check"]["escaped"]:
        escaped.append({"file": "tests/MessagePack.SourceGenerator.Tests/Resources/x", "id": "shape-preserving sweep"})
    for x in escaped:
        st = ledger.states_for([x["file"]], trust)[x["file"]]
        actions.append({"module": st["module"], "from": st["state"], "to": demote[st["state"]], "because": x["id"]})

    real_acc = sum(x["accusations"] for x in real)
    real_rej = sum(x["rejected"] for x in real)
    report = {
        "generated_at": ledger.now(),
        "seconds": round(time.time() - t0, 1),
        "replay": {"source": "replay (4 real branches, offline, LLM off)", "branches": real},
        "seeded": {"source": "seeded (bench/mutate.py)", "mutants": seeded, "total": len(seeded),
                   "caught": len(caught), "flagged": len(flagged),
                   "recall_reached_human": round(len(caught) / len(seeded), 3),
                   "recall_flagged": round(len(flagged) / len(seeded), 3)},
        "shape_preserving_sweep": {"source": "seeded (one attribute swap per snapshot of #2297)", **sweeps},
        "judge": judge_seeds(bases),
        "hallucinations_real": {"source": "replay (our LLM-written concept draft's findings)", "accusations": real_acc,
                                "rejected": real_rej, "rate": round(real_rej / real_acc, 3) if real_acc else None},
        "precision": precision(bases),
        "trust": {"source": f"upstream git history ({trust['window']}, {trust['commits_in_window']} commits)",
                  "counts": {s: sum(1 for m in trust["modules"].values() if m["state"] == s) for s in ("EARNED", "PROBATION", "REVOKED")}},
        "guardrail": {"source": "seeded escapes → trust demotion", "actions": actions},
        "sessions": sessions(),
    }
    OUT.write_text(json.dumps(report, indent=1))
    s = report["seeded"]
    print(f"seeded: {s['caught']}/{s['total']} reached a human ({s['flagged']} flagged) · "
          f"shape-preserving escapes: {sweeps['shape_only']['escaped']}/{sweeps['shape_only']['mutants']} shape-only, "
          f"{sweeps['with_content_check']['escaped']}/{sweeps['with_content_check']['mutants']} with content check · "
          f"judge: {report['judge']['rejected']}/{report['judge']['corruptions']} corruptions rejected, "
          f"{report['judge']['accepted']}/{report['judge']['controls']} controls kept · "
          f"precision: {report['precision']['precision']} · {report['seconds']}s → {OUT.relative_to(ROOT)}")
    for x in seeded:
        print(f"  {x['id']} {x['result']:<8} {x['branch'][-4:]} {x['what'][:70]}  {', '.join(x['caught_by'])}")
    return report


if __name__ == "__main__":
    main()
