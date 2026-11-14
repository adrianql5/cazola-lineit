"""Stages 5-7: Abstention Gate, Risk Router and Spot-check sampler.

All three are rules a person can read, not scores. No percentage of
confidence is produced anywhere.
"""

from __future__ import annotations

import math
import random

from . import config, ledger
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
    "critical-operation": "the owners of that area",
    "critical-untested": "the owners of that area",
}


def abstentions(change: Change, cl: dict, trace: dict, judged: dict, sens: dict | None = None) -> list[dict]:
    out = []

    def add(kind, decision, why, missing, options, cite, who=None):
        out.append({"id": f"ABS-{len(out) + 1}", "status": "ABSTAINED", "kind": kind, "decision": decision,
                    "why_not_ai": why, "missing_evidence": missing, "who_decides": who or WHO[kind],
                    "options": options, "cite": cite})

    # Critical operations first: they are the decisions that matter most.
    sens = sens or {"zones": [], "escalations": []}
    seen = set()
    for z in sens["zones"]:
        if z["name"] in seen:
            continue
        seen.add(z["name"])
        who = ("@" + " or @".join(z["owners"])) if z["owners"] else "the owners of that code (no owner is declared for it)"
        removed = " (a line removed)" if z.get("removed") else ""
        where = f"`{z['file'].rsplit('/', 1)[-1]}:{z['line']}`{removed}"
        if z.get("caller"):
            c = z["caller"]
            question = (f"{where} is used by `{c['file'].rsplit('/', 1)[-1]}:{c['line']}` ({c['text']}). "
                        "Is the new behaviour still correct there?")
        else:
            question = f"This change touches {z['name']} at {where}. Is its behaviour correct?"
        add("critical-operation", question,
            f"It is critical because {z['why']}. The AI does not judge whether critical logic is right; its owner does.",
            ["the owner's reading of the code", "a test that covers this behaviour"], ["approve", "request-changes"],
            f"{z['file']}:{z['line']}", who)
    if any(e["rule"] == "CRITICAL-UNTESTED" for e in sens["escalations"]):
        z = sens["zones"][0]
        add("critical-untested", "This critical change has no passing test run. Merge it anyway?",
            "Accepting critical code without tests is a risk only its owner can take.",
            ["a passing run of tests that cover the critical lines"], ["merge-without-tests", "wait-for-tests"],
            f"{z['file']}:{z['line']}", ("@" + " or @".join(z["owners"])) if z["owners"] else None)

    trig = {}
    for t in cl["triggers"]:
        trig.setdefault(t["rule"], t)
    if "T2-PUBLIC-API" in trig:
        t = trig["T2-PUBLIC-API"]
        add("public-api", f"Is the new public API (`{t['text'].split(':')[0].replace('public ', '').replace('class ', '').strip()}`) the right shape to support for years?",
            "Public API is a long-term promise. Tests show it works, not that it is the right design.",
            ["API review by a maintainer", "a PublicAPI.Unshipped.txt entry (none in this diff)"],
            ["approve-shape", "request-changes"], f"{t['file']}:{t['line']}")
    if "T2-SERIALIZATION-CONTRACT" in trig:
        t = trig["T2-SERIALIZATION-CONTRACT"]
        add("serialization-contract", "Should these types be saved with every public property, keyed by name, by default?",
            "The default wire format affects every message ever saved with it.",
            ["the maintainers' position on contractless as a default", "round-trip tests against data written by an older version"],
            ["accept-contractless-default", "require-explicit-surrogate"], f"{t['file']}:{t['line']}")
    if "T2-ANALYZER-SEVERITY" in trig:
        t = trig["T2-ANALYZER-SEVERITY"]
        add("analyzer-severity", "Should the new rules break users' builds (Error) or only warn?",
            "Breaking other people's builds is a policy choice, not a code question.",
            ["maintainers' severity policy for new rules"], ["keep-error", "downgrade-to-warning"], f"{t['file']}:{t['line']}")
    if "T2-UNSAFE" in trig:
        t = trig["T2-UNSAFE"]
        add("security", "Is the unsafe or generated-at-runtime code acceptable here?",
            "Memory safety and runtime code generation need a security reviewer.",
            ["a security review"], ["approve", "reject"], f"{t['file']}:{t['line']}")
    for row in trace["claims"]:
        if row["status"] == "CONTRADICTED" and row["id"].startswith("REQ"):
            c = row["contradictions"][0]
            add("compatibility", "Keep or remove the guard that leaves out netstandard2.0 and .NET Framework?",
                "Which platforms get a feature is a promise to users. The AI shows the gap and the docs; a person decides.",
                ["the PR author's reason for the guard", "a test compiled for netstandard2.0 / net472 consumers"],
                ["keep-guard", "remove-guard"], f"{c['file']}:{c['line']}")
    alts = trace.get("alternatives", [])
    if alts and not any(a["chosen"] for a in alts):
        add("ambiguous-requirement", f"The issue suggested {len(alts)} designs; the change uses a different one (`SurrogateType`). Is that OK?",
            "Choosing between designs the issue left open is the issue owner's call.",
            ["the issue author's choice", "maintainers' preference"], ["accept-surrogate-design", "ask-issue-author"],
            trace["requirements_source"])
    for v in judged["accepted"]:
        if v["id"] == "P-GLOBAL-WRAP":
            add("diagnostic-policy", "Is it OK to drop every diagnostic without a source location, not only those from other assemblies?",
                "Which warnings users may lose is the analyzer owners' call.",
                ["a test showing a diagnostic of the compilation's own type with a null location is still reported"],
                ["accept-global-filter", "narrow-to-metadata-types"], f"{v['file']}:{v['line_start']}")
    return out


# --- 6. Risk Router --------------------------------------------------------

def route(change: Change, cl: dict, trust: dict, abst: list[dict], sens: dict | None = None) -> dict:
    sens = sens or {"zones": [], "escalations": [], "files": []}
    files = {f["path"]: f for f in cl["files"]}
    states = ledger.states_for(list(files), trust)
    reasons = []
    t2 = sorted({t["rule"] for t in cl["triggers"]})
    semantic = [p for p, f in files.items() if f["category"] in ("semantic", "public-contract")]
    if sens["zones"]:
        tier = "T2"
        names = sorted({z["name"] for z in sens["zones"]})
        reasons.append(f"critical operation: {', '.join(names)}")
        reasons += [f"{r}: {next(t['why'] for t in cl['triggers'] if t['rule'] == r)}" for r in t2]
        reasons += [e["why"] for e in sens["escalations"]]
    elif t2:
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
    lowered = sorted({states[p]["module"] for p in mech if states[p].get("lowered_by")})
    if lowered:
        why = trust["modules"][lowered[0]]["lowered_by"][-1]
        reasons.append(f"generated files in {', '.join(lowered)} are read in full: trust was lowered after a {why}")
        if tier == "T0":
            tier = "T1"
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
        if f["category"] == "mechanical" and st != "REVOKED" and p not in sens["files"]:  # critical files are never hidden
            hidden.append(p)
        elif tier == "T2" or f["category"] in ("semantic", "public-contract", "docs", "mechanical") or p.endswith(".csproj"):
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

def sample(change: Change, hidden: list[str], rate: float | None = None) -> dict:
    rate = config.get()["review"]["sample_rate"] if rate is None else rate
    pop = sorted(hidden)
    if not pop:
        return {"stage": "sampler", "population": 0, "sample": [], "seed": None,
                "method": "nothing hidden, nothing to sample"}
    n = max(1, math.ceil(rate * len(pop)))
    seed = int(change.sha[:16], 16)
    picked = sorted(random.Random(seed).sample(pop, n))
    return {"stage": "sampler", "population": len(pop), "rate": rate, "n": n, "seed": change.sha[:16],
            "method": f"random.Random(int(commit_sha[:16], 16)).sample(sorted(hidden files), max(1, ceil({rate} x N)))",
            "sample": picked, "proof_lines": proof_lines(change, pop, picked)}


def squash(text: str) -> str:
    return "".join(text.split())


def proof_lines(change: Change, hidden: list[str], picked: list[str]) -> dict[str, list[str]]:
    """Lines shown in each sampled file's diff that few other hidden files
    have: quoting one proves the reviewer opened that file."""
    files = {f.path: f for f in change.files}
    seen: dict[str, int] = {}
    for p in hidden:
        if p not in files:
            continue
        for t in {squash(l.text) for h in files[p].hunks for l in h.lines if l.kind != "-"}:
            seen[t] = seen.get(t, 0) + 1
    limit = max(1, len(hidden) // 20)
    out = {}
    for p in picked:
        if p not in files:
            continue
        lines = {squash(l.text) for h in files[p].hunks for l in h.lines if l.kind != "-"}
        out[p] = sorted(t for t in lines if len(t) >= 12 and seen.get(t, 0) <= limit)
    return out
