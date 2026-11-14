"""Stage: Sensitivity. Which parts of a change are critical (money, security,
data, untrusted input, or an area the team declared), who must sign for
them, and what the situation adds.

Four layers, each one can only *raise* the review, never lower it:
1. declared: critical areas in .earned-trust.toml, with their owners;
2. detected: built-in patterns over the changed lines (deleted lines too:
   removing a balance check is as critical as adding one);
3. AI: the model is asked which changed lines are sensitive; every answer
   must cite file, line and symbol, and goes through the judge;
   (and reach: a file outside a declared area whose types the area's code
   uses, on the base branch, is critical too: changing a helper changes
   the critical code that calls it);
4. situation: critical and untested, critical in a folder that lost trust,
   critical inside generated files.

Owners come from the area's `owners`, or from CODEOWNERS for the file.
"""

from __future__ import annotations

import json
import re

from . import config, judge, ledger, llm
from .sources import FACTORY, Change

DETECTORS: dict[str, list[tuple[str, str, str]]] = {
    "money": [
        ("money held in floating point",
         r"(?i)\b(double|float|single)\b[^;\n]*\b(amount|balance|price|fee|total|interest|rate)\w*|"
         r"\b(amount|balance|price|fee|total)\w*\b[^;\n]*\(\s*(double|float)\s*\)",
         "binary floating point cannot hold amounts like 0.10 exactly, so money rounds wrongly"),
        ("money movement",
         r"(?i)\b(balance|amount|transfer|withdraw|deposit|payment|iban|currency|exchange.?rate|interest|"
         r"overdraft|refund|invoice|ledger)\w*\b",
         "it moves money or computes amounts"),
    ],
    "security": [
        ("secrets and credentials", r"(?i)\b(password|passwd|secret|api.?key|private.?key|access.?token|credential)s?\b",
         "it handles secrets or credentials"),
        ("cryptography", r"\b(Encrypt|Decrypt|HMAC\w*|RandomNumberGenerator|MD5|SHA1|Aes\w*|RSA\w*)\b|(?i:\b(encrypt|decrypt|hmac)\w*\()",
         "it changes cryptography"),
        ("access control", r"(?i)\b(authoriz|authenticat|permission|isadmin|access.?control)\w*",
         "it decides who may do what"),
    ],
    "data": [
        ("data deletion or schema change",
         r"(?i)\b(DELETE\s+FROM|DROP\s+(TABLE|DATABASE)|TRUNCATE\s+TABLE|ALTER\s+TABLE)\b|\.(RemoveRange|DeleteMany)\(",
         "it deletes data or changes a schema"),
        ("personal data", r"(?i)\b(ssn|social.?security|passport|date.?of.?birth|national.?id)\b",
         "it handles personal data"),
    ],
    "untrusted-input": [
        ("deserializing untrusted data",
         r"\b(UntrustedData|MessagePackSecurity|BinaryFormatter|TypeNameHandling)\b|pickle\.loads|yaml\.load\(|\beval\(",
         "it reads data that may come from an attacker"),
    ],
}

PROMPT_VERSION = "sensitivity-v1"
SYSTEM = """You review a code change. List the changed lines that touch something critical:
moving or computing money, security (credentials, cryptography, access control), deleting data,
personal data, or reading untrusted input. Answer ONLY with a JSON array, at most 5 items:
{"file": str, "line_start": int, "line_end": int, "symbol": str (an identifier written on those lines),
"area": str (2 or 3 words), "why": str (one short sentence)}. Use the line numbers given after L.
If nothing is critical, answer []."""


# --- reach: the base branch's files inside declared areas ------------------

_base_files: dict[str, str] = {}


def use_base(files: dict[str, str] | None) -> None:
    """The files inside declared critical areas, as they are on the base
    branch (read by github.load_settings). Empty: the reach check is skipped."""
    global _base_files
    _base_files = dict(files or {})


DECLARES = re.compile(r"\b(?:class|record|struct|interface|enum)\s+([A-Z]\w{3,})")


def declared_types(f) -> set[str]:
    """Type names a changed file declares: its C#-style file name, and the
    types declared on the lines the diff shows."""
    stem = f.path.rsplit("/", 1)[-1].split(".")[0]
    names = {stem} if f.path.endswith(".cs") and stem[:1].isupper() and len(stem) >= 4 else set()
    for h in f.hunks:
        for l in h.lines:
            names |= set(DECLARES.findall(l.text))
    return names


def callers(names: set[str], area: dict) -> tuple[str, int, str, str] | None:
    """The first line inside AREA (base branch) that uses one of NAMES."""
    for path in sorted(_base_files):
        if not any(re.search(p, path) for p in area["paths"]):
            continue
        for no, text in enumerate(_base_files[path].splitlines(), 1):
            for n in sorted(names):
                if re.search(rf"\b{re.escape(n)}\b", text) and not DECLARES.search(text):
                    return path, no, text.strip()[:140], n
    return None


# --- CODEOWNERS ------------------------------------------------------------

def _glob_to_regex(pattern: str) -> str:
    anchored = pattern.startswith("/")
    p = pattern.strip("/") if pattern.endswith("/") else pattern.lstrip("/")
    directory = pattern.endswith("/")
    out = ""
    i = 0
    while i < len(p):
        if p.startswith("**", i):
            out += ".*"
            i += 2
        elif p[i] == "*":
            out += "[^/]*"
            i += 1
        else:
            out += re.escape(p[i])
            i += 1
    if directory:
        out += "/.*"
    else:
        out += "(/.*)?"
    prefix = "^" if anchored or "/" in pattern.strip("/") else "^(.*/)?"
    return prefix + out + "$"


def code_owners(path: str, text: str | None = None) -> tuple[list[str], list[str]]:
    """The users CODEOWNERS names for PATH (the last matching line wins), and
    any teams it names, which this tool cannot resolve to people."""
    text = config.codeowners() if text is None else text
    users, teams = [], []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        pattern, *owners = line.split()
        if re.match(_glob_to_regex(pattern), path):
            users = [o.lstrip("@") for o in owners if o.startswith("@") and "/" not in o]
            teams = [o.lstrip("@") for o in owners if o.startswith("@") and "/" in o]
    return users, teams


# --- the stage -------------------------------------------------------------

def changed_lines(f):
    for h in f.hunks:
        for l in h.lines:
            if l.kind != " ":
                yield l


def owners_for(files: list[str], declared: list[str]) -> tuple[list[str], list[str]]:
    if declared:
        return declared, []
    users, teams = [], []
    for p in files:
        u, t = code_owners(p)
        users += [x for x in u if x not in users]
        teams += [x for x in t if x not in teams]
    return users, teams


def ask_ai(change: Change, cl: dict, offline: bool) -> tuple[list[dict], dict]:
    from .prosecutor import numbered
    user = f"Change: {change.subject}\n\n{numbered(change, cl, limit=40000)}"
    try:
        r = llm.chat(SYSTEM, user, prompt_version=PROMPT_VERSION,
                     cache_dir=FACTORY / "cache" / change.branch / "llm", offline=offline)
        items = llm.extract_json(r["content"])
    except (llm.LLMUnavailable, ValueError) as e:
        return [], {"status": "NOT RUN", "why": str(e)}
    out = []
    for a in items if isinstance(items, list) else []:
        acc = {"id": f"AI-SENS-{len(out) + 1}", "source": f"llm: {r['model']}", "claim": a.get("why", ""),
               "file": a.get("file"), "line_start": a.get("line_start"), "line_end": a.get("line_end"),
               "symbol": a.get("symbol"), "area": a.get("area", "critical")}
        out.append(judge.verdict(acc, change.files))
    return out, {"status": "RAN", "model": r["model"]}


def run(change: Change, cl: dict, trace: dict, offline: bool = True, use_llm: bool = True) -> dict:
    cfg = config.get()
    cats = {f["path"]: f["category"] for f in cl["files"]}
    eligible = [f for f in change.files if cats.get(f.path) in ("semantic", "public-contract", "mechanical")]
    zones: list[dict] = []

    # 1. declared areas
    for area in cfg["critical"]:
        hit = [f for f in change.files if any(re.search(p, f.path) for p in area["paths"])]
        if not hit:
            continue
        first = next(changed_lines(hit[0]), None)
        users, teams = owners_for([f.path for f in hit], area["owners"])
        zones.append({"name": area["name"], "source": "declared in " + config.FILE, "files": [f.path for f in hit],
                      "file": hit[0].path, "line": (first.new_no or first.old_no) if first else None,
                      "text": first.text.strip()[:140] if first else "", "why": "the team declared this area critical",
                      "owners": users, "teams": teams, "signatures": area["signatures"], "evidence": []})

    def inside(path: str) -> dict | None:
        return next((z for z in zones if z["source"].startswith("declared") and path in z["files"]), None)

    # 1b. reach: helpers that a declared area calls
    for area in cfg["critical"]:
        for f in eligible:
            if inside(f.path) or any(re.search(p, f.path) for p in area["paths"]):
                continue
            hit = callers(declared_types(f), area)
            if not hit:
                continue
            path, no, text, name = hit
            first = next((l for l in changed_lines(f) if l.kind == "+"), None) or next(changed_lines(f), None)
            users, teams = owners_for([path], area["owners"])
            zones.append({"name": f"{area['name']} (through {name})", "source": f"used from {area['name']}",
                          "files": [f.path], "file": f.path, "line": (first.new_no or first.old_no) if first else None,
                          "text": first.text.strip()[:140] if first else "", "removed": bool(first and first.kind == "-"),
                          "why": f"`{name}` is used by {area['name']} code at {path}:{no} (`{text}`), "
                                 f"so changing it changes how {area['name']} behaves",
                          "caller": {"file": path, "line": no, "text": text},
                          "owners": users, "teams": teams, "signatures": area["signatures"], "evidence": []})

    # 2. detected by pattern
    detectors = [(d, *x) for d in cfg["sensitivity"]["detectors"] for x in DETECTORS.get(d, [])]
    detectors += [("extra", x["name"], x["pattern"], x.get("why", "your own pattern")) for x in cfg["sensitivity"]["extra"]]
    for kind, label, pattern, why in detectors:
        for f in eligible:
            line = next((l for l in changed_lines(f) if re.search(pattern, l.text)), None)
            if not line:
                continue
            ev = {"detector": label, "file": f.path, "line": line.new_no or line.old_no,
                  "removed": line.kind == "-", "text": line.text.strip()[:140], "why": why}
            z = inside(f.path)
            if z:
                z["evidence"].append(ev)
                continue
            if any(x["source"] == "detected" and x["name"] == label and x["file"] == f.path for x in zones):
                continue
            users, teams = owners_for([f.path], [])
            zones.append({"name": label, "source": "detected", "files": [f.path], "file": f.path, "line": ev["line"],
                          "text": ev["text"], "removed": ev["removed"], "why": why, "owners": users, "teams": teams,
                          "signatures": 1, "evidence": []})

    # a declared area points at its most telling line: what a detector found, not its first change
    for z in zones:
        if z["source"].startswith("declared") and z["evidence"]:
            e = z["evidence"][0]
            z.update(file=e["file"], line=e["line"], text=e["text"], removed=e["removed"],
                     why=f"the team declared this area critical, and {e['why']}")

    # 3. the AI, judge-checked, can only add
    ai = {"status": "NOT RUN", "why": "turned off in the settings" if not cfg["sensitivity"]["ai"] else "no AI for this run"}
    if cfg["sensitivity"]["ai"] and use_llm:
        verdicts, ai = ask_ai(change, cl, offline)
        ai["rejected"] = [v for v in verdicts if v["verdict"] == "REJECTED"]
        for v in verdicts:
            if v["verdict"] != "ACCEPTED":
                continue
            z = inside(v["file"])
            ev = {"detector": f"AI: {v['area']}", "file": v["file"], "line": v["line_start"], "removed": False,
                  "text": v["evidence"][0]["text"].strip()[:140] if v.get("evidence") else "", "why": v["claim"]}
            if z:
                z["evidence"].append(ev)
                continue
            users, teams = owners_for([v["file"]], [])
            zones.append({"name": v["area"], "source": f"AI ({ai.get('model', '')}), citation checked",
                          "files": [v["file"]], "file": v["file"], "line": v["line_start"], "text": ev["text"],
                          "why": v["claim"], "owners": users, "teams": teams, "signatures": 1, "evidence": []})

    # 4. the situation
    escalations = []
    if zones:
        ex = trace["execution"]
        if ex.get("status") != "PASS":
            escalations.append({"rule": "CRITICAL-UNTESTED", "effect": "decision",
                                "why": "critical code without a passing test run: a person decides whether to merge anyway"})
        trust = ledger.trust_table()
        files = sorted({p for z in zones for p in z["files"]})
        low = sorted({s["module"] for p, s in ledger.states_for(files, trust).items() if s["state"] == "REVOKED"})
        if low:
            escalations.append({"rule": "CRITICAL-LOW-TRUST", "effect": "one more signature",
                                "why": f"critical code in {', '.join(low)}, whose trust is revoked"})
        gen = sorted({p for z in zones for p in z["files"] if cats.get(p) == "mechanical"})
        if gen:
            escalations.append({"rule": "CRITICAL-GENERATED", "effect": "never hidden",
                                "why": f"critical changes inside generated files ({len(gen)}): they are read, not sampled"})

    need = max([z["signatures"] for z in zones] or [1])
    if any(e["rule"] == "CRITICAL-LOW-TRUST" for e in escalations):
        need += 1
    groups = [{"zone": z["name"], "owners": z["owners"]} for z in zones if z["owners"]]
    return {"stage": "sensitivity", "zones": zones, "escalations": escalations, "ai": ai,
            "required": {"signatures": need if zones else 1, "owner_groups": groups},
            "files": sorted({p for z in zones for p in z["files"]})}
