"""Runs the stages in order; each writes runs/<branch>/<stage>.json and the
next one reads it. In CI, factory/earned_trust/github.py runs it on every
pull request."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import auditor, brief, classifier, gate, judge, ledger, prosecutor, sources, tracer
from .sources import FACTORY, Change

RUNS = FACTORY.parent / "runs"
# the routing policy is these files: their hash goes into every receipt
POLICY_FILES = [FACTORY / "earned_trust" / "gate.py", FACTORY / "earned_trust" / "classifier.py"]
STAGES = ["classifier", "tracer", "auditor", "prosecutor", "judge", "abstention", "router", "sampler"]


def dedupe(accepted: list[dict]) -> list[dict]:
    """Two sources citing the same line about the same symbol are one finding."""
    out: list[dict] = []
    for f in accepted:
        same = next((g for g in out if g["file"] == f["file"] and g["line_start"] == f["line_start"]
                     and g["symbol"] == f["symbol"]), None)
        if same:
            same.setdefault("also_raised_by", []).append(f"{f['id']} ({f['source']})")
            if f.get("phantom_test") and not same.get("phantom_test"):
                same["phantom_test"] = f["phantom_test"]
        else:
            out.append(dict(f))
    return out


def not_checked(r: dict) -> list[dict]:
    out = []
    ex = r["tracer"]["execution"]
    if ex["status"] != "PASS":
        out.append({"item": "Running the tests (`dotnet build`, `dotnet test`)", "why": f"{ex['status']}: {ex.get('why', '')}"})
    else:
        out.append({"item": "The rest of the test suite", "why": f"only the {ex['passed']} tests this change adds were run ({ex['how']}, {ex['ran_at']})"})
        if ex.get("deviations"):
            out.append({"item": "The pinned build environment", "why": "; ".join(ex["deviations"])})
        if any(t["rule"] == "T2-TEST-EXCLUSION" for t in r["classifier"]["triggers"]):
            out.append({"item": "Tests excluded from another test project", "why": "excluded tests were not run there (see the T2-TEST-EXCLUSION trigger)"})
    out.append({"item": "Semantic analysis with Roslyn", "why": "classification is diff heuristics + regex (Roslyn classifier is P2)"})
    llm = r["prosecutor"]["llm"]
    if llm["status"] != "RAN":
        out.append({"item": "LLM prosecution", "why": f"{llm['status']}: {llm.get('why', '')} — deterministic only for this run"})
    un = [c["id"] for c in r["tracer"]["claims"] if c["status"] == "UNVERIFIED"]
    if un:
        out.append({"item": f"Claims {', '.join(un)}", "why": "no test in this change covers them"})
    s = r["sampler"]
    if s["population"]:
        out.append({"item": f"{s['population'] - s['n']} of {s['population']} hidden mechanical files", "why": "not sampled; covered by the pattern check only"})
    if r["judge"]["accepted"]:
        out.append({"item": "Whether each finding's argument is right", "why": "the judge checks citations only; a human accepts or refutes"})
    return out


class Run:
    """One review of one change: its stages' JSON in RUN_DIR."""

    def __init__(self, change: Change, run_dir: Path | None = None, *, offline: bool = True, use_llm: bool = True,
                 write: bool = True):
        self.change, self.offline, self.use_llm, self.write = change, offline, use_llm, write
        self.dir = run_dir or RUNS / change.branch
        self.r: dict = {}

    def get(self, name: str) -> dict:
        if name not in self.r:
            p = self.dir / f"{name}.json"
            if not p.exists():
                raise RuntimeError(f"stage `{name}` has not run for {self.change.branch} (run it first)")
            self.r[name] = json.loads(p.read_text())
        return self.r[name]

    def put(self, name: str, value) -> None:
        self.r[name] = value
        if self.write:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / f"{name}.json").write_text(json.dumps(value, indent=1))

    def stage(self, name: str) -> dict:
        c = self.change
        if name == "classifier":
            self.put(name, classifier.run(c))
        elif name == "tracer":
            facts = json.loads((FACTORY / "knowledge" / "facts.json").read_text())["facts"]
            self.put(name, tracer.run(c, self.dir, facts))
        elif name == "auditor":
            self.put(name, auditor.run(c, self.get("classifier"), self.get("tracer")))
        elif name == "prosecutor":
            self.put(name, prosecutor.run(c, self.get("classifier"), offline=self.offline, use_llm=self.use_llm))
        elif name == "judge":
            jd = judge.run(self.get("auditor")["findings"] + self.get("prosecutor")["accusations"], c.files)
            jd["accepted"] = dedupe(jd["accepted"])
            self.put(name, jd)
        elif name == "abstention":
            self.put(name, gate.abstentions(c, self.get("classifier"), self.get("tracer"), self.get("judge")))
        elif name == "router":
            self.put(name, gate.route(c, self.get("classifier"), ledger.trust_table(), self.get("abstention")))
        elif name == "sampler":
            self.put(name, gate.sample(c, self.get("router")["hidden"]))
        elif name == "brief":
            return self.finish()
        else:
            raise ValueError(f"no stage `{name}`; stages: {', '.join(STAGES)}, brief")
        return self.r[name]

    def finish(self) -> dict:
        c = self.change
        trust = ledger.trust_table()
        r = {k: self.get(k) for k in STAGES}
        r["abstentions"] = r.pop("abstention")
        pr = r["prosecutor"]
        policy_sha = hashlib.sha256(b"".join(p.read_bytes() for p in POLICY_FILES)).hexdigest()
        r["change"] = {"branch": c.branch, "issue": c.issue, "sha": c.sha, "subject": c.subject, "author": c.author,
                       "issue_title": c.issue_title, "issue_url": c.issue_url, "files": len(c.files),
                       "added": c.added, "deleted": c.deleted, "diff_sha": c.diff_sha, "source": c.source}
        r["provenance"] = {
            "llm": (f"RAN ({pr['llm'].get('model', '')}, {pr['llm'].get('prompt_version', '')}"
                    f"{', from replay cache' if pr['llm'].get('cached') else ''})"
                    if pr["llm"]["status"] == "RAN" else f"{pr['llm']['status']}: {pr['llm'].get('why', '')}"),
            "policy_sha": policy_sha,
            "trust": f"{trust['source']}, {trust['window']}",
        }
        r["not_checked"] = not_checked(r)
        self.r["report"] = r
        if self.write:
            (self.dir / "report.json").write_text(json.dumps(r, indent=1))
            (self.dir / "brief.md").write_text(brief.render(r))
        return r


def review(change: Change, *, offline: bool = True, use_llm: bool = True, run_dir: Path | None = None,
           write: bool = True) -> dict:
    run = Run(change, run_dir, offline=offline, use_llm=use_llm, write=write)
    for s in STAGES:
        run.stage(s)
    if write and (run.dir / "state.json").exists():
        (run.dir / "state.json").unlink()  # a new brief starts a new gate
    return run.finish()


def load_report(branch: str) -> dict:
    return json.loads((RUNS / branch / "report.json").read_text())


def change_for(branch: str, offline: bool = True) -> Change:
    return sources.load(branch, offline=offline)
