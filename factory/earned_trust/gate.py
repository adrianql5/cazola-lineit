"""Stages 5-7: Abstention Gate, Risk Router and Spot-check sampler.

All three are rules a person can read, not scores. No percentage of
confidence is produced anywhere.
"""

from __future__ import annotations

import math
import random

from . import ledger
from .sources import Change

# --- 5. Abstention Gate ----------------------------------------------------

WHO = {
    "public-api": "the package maintainers (API owners of MessagePack.Annotations)",
    "serialization-contract": "the package maintainers: the wire format is a promise to every user",
    "compatibility": "the PR owner, with the maintainers for supported target frameworks",
    "diagnostic-policy": "the analyzer maintainers",
    "security": "a security reviewer",
    "ambiguous-requirement": "the issue author and the maintainers",
    "analyzer-severity": "the analyzer maintainers: a new Error breaks users' builds on upgrade",
}


def abstentions(change: Change, cl: dict, trace: dict, judged: dict) -> list[dict]:
    out = []

    def add(kind, decision, why, missing, options, cite):
        out.append({"id": f"ABS-{len(out) + 1}", "status": "ABSTAINED", "kind": kind, "decision": decision,
                    "why_not_ai": why, "missing_evidence": missing, "who_decides": WHO[kind],
                    "options": options, "cite": cite})

    trig = {}
    for t in cl["triggers"]:
        trig.setdefault(t["rule"], t)
    if "T2-PUBLIC-API" in trig:
        t = trig["T2-PUBLIC-API"]
        add("public-api", f"Is `{t['text'].split(':')[0].replace('public ', '').strip()}` the public API the package wants to support forever?",
            "Public API in a published package is a product commitment; tests can show it works, not that it is the right shape.",
            ["API review by a maintainer", "a PublicAPI.Unshipped.txt entry (none in this diff)"],
            ["approve-shape", "request-changes"], f"{t['file']}:{t['line']}")
    if "T2-SERIALIZATION-CONTRACT" in trig:
        t = trig["T2-SERIALIZATION-CONTRACT"]
        add("serialization-contract", "Should the default for these types be contractless (every public read-write member, keyed by its name)?",
            "The default wire contract decides compatibility of every message ever written with it; that is a product decision.",
            ["the maintainers' position on contractless as a default", "round-trip tests against data written by an older version"],
            ["accept-contractless-default", "require-explicit-surrogate"], f"{t['file']}:{t['line']}")
    if "T2-ANALYZER-SEVERITY" in trig:
        t = trig["T2-ANALYZER-SEVERITY"]
        add("analyzer-severity", "Should the new diagnostics ship as Error (build-breaking) rather than Warning?",
            "Severity is policy about users' builds, not a property of the code.",
            ["maintainers' severity policy for new rules"], ["keep-error", "downgrade-to-warning"], f"{t['file']}:{t['line']}")
    if "T2-UNSAFE" in trig:
        t = trig["T2-UNSAFE"]
        add("security", "Is the unsafe / dynamic code acceptable here?",
            "Memory safety and code generation at run time need a security reviewer.",
            ["a security review"], ["approve", "reject"], f"{t['file']}:{t['line']}")
    for row in trace["claims"]:
        if row["status"] == "CONTRADICTED" and row["id"].startswith("REQ"):
            c = row["contradictions"][0]
            add("compatibility", f"{row['id']} asks for \"{row['claim']}\" but the change leaves some targets out. Intended?",
                "Which target frameworks get a feature is a compatibility promise; the AI can show the gap (and the API docs), not decide it.",
                ["the PR author's reason for the guard", "a test compiled for netstandard2.0 / net472 consumers"],
                ["keep-guard", "remove-guard"], f"{c['file']}:{c['line']}")
    alts = trace.get("alternatives", [])
    if alts and not any(a["chosen"] for a in alts):
        add("ambiguous-requirement", "The issue lists " + str(len(alts)) + " ways to give keys for T and picks none; the change invents another (SurrogateType + contractless). Which one?",
            "Choosing between designs the issue left open is the requirement owner's call.",
            ["the issue author's choice", "maintainers' preference"], ["accept-surrogate-design", "ask-issue-author"],
            trace["requirements_source"])
    for v in judged["accepted"]:
        if v["id"] == "P-GLOBAL-WRAP":
            add("diagnostic-policy", "Is it acceptable that every diagnostic without a source location in this compilation is now dropped, not only those from referenced assemblies?",
                "Which diagnostics users may lose is analyzer policy; the AI can point at the filter, not weigh the trade-off.",
                ["a test showing a diagnostic of the compilation's own type with a null location is still reported"],
                ["accept-global-filter", "narrow-to-metadata-types"], f"{v['file']}:{v['line_start']}")
    return out


# --- 6. Risk Router --------------------------------------------------------

def route(change: Change, cl: dict, trust: dict, abst: list[dict]) -> dict:
    files = {f["path"]: f for f in cl["files"]}
    states = ledger.states_for(list(files), trust)
    reasons = []
    t2 = sorted({t["rule"] for t in cl["triggers"]})
    semantic = [p for p, f in files.items() if f["category"] in ("semantic", "public-contract")]
    if t2:
        tier = "T2"
        reasons += [f"{r}: {next(t['why'] for t in cl['triggers'] if t['rule'] == r)}" for r in t2]
    elif semantic or abst:
        tier = "T1"
        if semantic:
            n_out = sum(1 for p in semantic if files[p].get("group_role") == "outlier")
            n_sem = len(semantic) - n_out
            parts = [f"{n_sem} semantic file{'s' if n_sem != 1 else ''}"] if n_sem else []
            if n_out:
                parts.append(f"{n_out} outlier{'s' if n_out != 1 else ''}")
            reasons.append(" and ".join(parts) + " to read")
        if abst:
            reasons.append(f"{len(abst)} decision(s) the AI abstained from")
    else:
        tier = "T0"
        reasons.append("only mechanical, test and docs changes")
    mech = [p for p, f in files.items() if f["category"] == "mechanical"]
    if tier == "T0" and any(states[p]["state"] != "EARNED" for p in mech):
        tier = "T1"
        reasons.append("mechanical files are in a module that has not EARNED summary review")
    revoked = sorted({states[p]["module"] for p in semantic if states[p]["state"] == "REVOKED"})
    second = tier == "T2" and bool(revoked)
    if second:
        reasons.append(f"second reviewer required: module(s) {', '.join(revoked)} are REVOKED in the trust ledger")
    policy = "factory rules (earned_trust/gate.py + classifier.py)"

    # What the human must read, per tier
    hidden, must = [], []
    for p, f in files.items():
        st = states[p]["state"]
        if f["category"] == "mechanical" and st != "REVOKED":
            hidden.append(p)
        elif tier == "T2" or f["category"] in ("semantic", "public-contract", "docs") or p.endswith(".csproj"):
            must.append(p)
    lines_total = sum(f["added"] + f["deleted"] for f in files.values())
    lines_must = sum(files[p]["added"] + files[p]["deleted"] for p in must)
    lines_tests = sum(files[p]["added"] + files[p]["deleted"] for p in files if p not in must and p not in hidden)
    return {"stage": "router", "tier": tier, "policy": policy, "reasons": reasons, "second_reviewer": second,
            "module_states": {states[p]["module"]: states[p]["state"] for p in files},
            "read": {"files_total": len(files), "files_must_read": len(must), "files_hidden": len(hidden),
                     "lines_total": lines_total, "lines_must_read": lines_must,
                     "lines_tests_summarized": lines_tests,
                     "lines_hidden": lines_total - lines_must - lines_tests},
            "must_read": must, "hidden": hidden}


# --- 7. Spot-check sampler -------------------------------------------------

def sample(change: Change, hidden: list[str], rate: float = 0.05) -> dict:
    pop = sorted(hidden)
    if not pop:
        return {"stage": "sampler", "population": 0, "sample": [], "seed": None,
                "method": "nothing hidden, nothing to sample"}
    n = max(1, math.ceil(rate * len(pop)))
    seed = int(change.sha[:16], 16)
    picked = sorted(random.Random(seed).sample(pop, n))
    return {"stage": "sampler", "population": len(pop), "rate": rate, "n": n, "seed": change.sha[:16],
            "method": f"random.Random(int(commit_sha[:16], 16)).sample(sorted(hidden files), max(1, ceil({rate} x N)))",
            "sample": picked}
