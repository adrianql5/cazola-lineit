"""Stage 2: Requirement Tracer.

Two kinds of claims:
- REQ: what the issue asks for, curated by a human in factory/requirements
  (the requirement belongs to a person, not to the model);
- DOC: what the change says about itself, every sentence its README or docs
  add that names a diagnostic or a piece of code, extracted from the diff.

Each claim is joined to evidence: the diff lines that implement it, the tests
the diff adds that mention it, and whether those tests were run. A claim is
VERIFIED only with a passing run; without one the best it gets is PARTIAL.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .sources import FACTORY, Change

TEST_ATTR = re.compile(r"^\s*\[(Fact|Theory)\b")
TEST_SIG = re.compile(r"\b(?:async\s+)?(?:Task|void)\s+(\w+)\s*\(")
DIAG_RE = re.compile(r"MsgPack0\d\d")
CODE_RE = re.compile(r"`([^`]{3,80})`")


def test_methods(change: Change) -> list[dict]:
    """The [Fact]/[Theory] methods the diff adds, each with its body text."""
    out = []
    for f in change.files:
        if not f.path.startswith("tests/") or not f.path.endswith(".cs"):
            continue
        for h in f.hunks:
            cur = None
            pending_attr = False
            for l in h.lines:
                if l.kind == "-":
                    continue
                if TEST_ATTR.match(l.text):
                    if cur:
                        out.append(cur)
                    cur, pending_attr = None, True
                    continue
                if pending_attr:
                    m = TEST_SIG.search(l.text)
                    if m:
                        cur = {"name": m.group(1), "file": f.path, "line": l.new_no, "body": "", "added": l.kind == "+"}
                        pending_attr = False
                        continue
                if cur is not None:
                    cur["body"] += l.text + "\n"
            if cur:
                out.append(cur)
        # a test that uses a constant of its class checks the constant's value
        consts = dict(re.findall(r'const string (\w+) = (.+);', "\n".join(l.text for l in f.added_lines())))
        for t in out:
            if t["file"] == f.path:
                for name, value in consts.items():
                    if re.search(rf"\b{name}\b", t["body"]):
                        t["body"] += f"\n// {name} = {value}"
    return [t for t in out if t["added"]]


def diagnostic_names(change: Change) -> dict[str, list[str]]:
    known = json.loads((FACTORY / "knowledge" / "diagnostics.json").read_text())["ids"]
    for f in change.files:
        for l in f.added_lines():
            m = re.search(r'public const string (\w+) = "(MsgPack\d+)"', l.text)
            if m:
                known.setdefault(m.group(2), []).append(m.group(1))
    return known


def execution(change: Change, run_dir: Path) -> dict:
    """Test results from the worker (dotnet test), if it ran."""
    p = run_dir / "tests.json"
    if p.exists():
        data = json.loads(p.read_text())
        if data.get("sha") == change.sha:
            return data
        return {"status": "NOT RUN", "why": f"tests.json is for another commit ({str(data.get('sha'))[:10]})"}
    return {"status": "NOT RUN", "why": "no `dotnet test` result for this commit (no .NET SDK in this environment; the worker image runs it)"}


def matching_tests(tokens: list[str], tests: list[dict]) -> list[dict]:
    hits = []
    for t in tests:
        text = t["name"] + "\n" + t["body"]
        found = [k for k in tokens if k and k in text]
        if found:
            hits.append({"test": t["name"], "file": t["file"], "line": t["line"], "matched": found[:4]})
    return hits


def status(impl: list, tests: list, run: dict, contradictions: list) -> tuple[str, str]:
    if contradictions:
        return "CONTRADICTED", contradictions[0]["why"]
    if impl and tests and run.get("status") == "PASS":
        dev = f" (environment deviation: {'; '.join(run['deviations'])})" if run.get("deviations") else ""
        return "VERIFIED", f"implemented, covered by {len(tests)} test(s) that ran and passed{dev}"
    if impl and tests:
        return "PARTIAL", f"implemented and covered by {len(tests)} test(s), but the tests were NOT RUN"
    if tests:
        ran = " (ran and passed)" if run.get("status") == "PASS" else ""
        return "PARTIAL", f"a test mentions it{ran}, but no implementing line was found"
    if impl:
        return "UNVERIFIED", "implemented, but no test in this change covers it"
    return "UNVERIFIED", "no implementing line and no test found"


def probe(change: Change, probes: list[dict]) -> list[dict]:
    hits = []
    for p in probes:
        for f in change.files:
            if not re.search(p["path"], f.path):
                continue
            for l in f.added_lines():
                if re.search(p["added"], l.text):
                    hits.append({"file": f.path, "line": l.new_no, "text": l.text.strip()[:140]})
                    break
    return hits


def doc_claims(change: Change, names: dict[str, list[str]]) -> list[dict]:
    claims = []
    for f in change.files:
        if not (f.path.endswith(".md") and ("README" in f.path or f.path.startswith("doc/"))):
            continue
        if "AnalyzerReleases" in f.path or f.path.endswith("/index.md"):
            continue
        for h in f.hunks:
            fenced = False
            for l in h.lines:
                if l.kind == "-":
                    continue
                if l.text.strip().startswith("```"):
                    fenced = not fenced
                    continue
                if l.kind != "+" or fenced:
                    continue
                c = claim(l, f.path, names)
                if c:
                    claims.append(c)
    return claims


def claim(l, path: str, names: dict[str, list[str]]) -> dict | None:
    """A claim from one added docs line, if it names something a test could check."""
    text = l.text.strip()
    if not text or text.startswith(("#", "|", "<!--")):
        return None
    ids = DIAG_RE.findall(text)
    code = []
    for c in CODE_RE.findall(text):
        c = c.strip("[]")
        if c.endswith(".md") or c in CS_WORDS or len(c) < 6:
            continue
        code.append(c)
    if not ids and not code:
        return None
    tokens = list(dict.fromkeys(ids + [n for i in ids for n in names.get(i, []) if not n.endswith("Id")] + code))
    return {"text": text.lstrip("-* "), "file": path, "line": l.new_no, "tokens": tokens}


CS_WORDS = {"partial", "public", "internal", "sealed", "static", "abstract", "class", "struct", "record"}


def run(change: Change, run_dir: Path, facts: list[dict] | None = None) -> dict:
    req_file = FACTORY / "requirements" / f"{change.issue}.json"
    spec = json.loads(req_file.read_text()) if req_file.exists() else {"requirements": [], "alternatives": []}
    tests = test_methods(change)
    exe = execution(change, run_dir)
    names = diagnostic_names(change)
    facts = facts or []
    rows = []
    for r in spec["requirements"]:
        impl = probe(change, r.get("implements", []))
        cov = matching_tests(r.get("tests", []), tests)
        contra = []
        for c in r.get("contradicts", []):
            for hit in probe(change, [c]):
                contra.append({**hit, "why": c["why"], "fact": c.get("fact")})
        st, why = status(impl, cov, exe, contra)
        rows.append({"id": r["id"], "kind": r["kind"], "claim": r["text"], "quote": r.get("quote", ""),
                     "implementation": impl, "tests": cov, "execution": exe["status"],
                     "contradictions": contra, "status": st, "why": why})
    for i, c in enumerate(doc_claims(change, names), 1):
        cov = matching_tests(c["tokens"], tests)
        contra = []
        for fact in facts:
            if re.search(fact["contradicted_by"], c["text"]):
                contra.append({"file": c["file"], "line": c["line"], "text": c["text"][:140],
                               "why": f"contradicted by {fact['id']}: {fact['statement']}", "fact": fact["id"]})
        impl = [{"file": c["file"], "line": c["line"], "text": "(the change's own documentation)"}]
        st, why = status(impl, cov, exe, contra)
        if not cov and not contra:
            why = "documented, but no test in this change mentions " + ", ".join(f"`{t}`" for t in c["tokens"][:3])
        rows.append({"id": f"DOC-{change.issue}-{i}", "kind": "claim the change makes in its docs", "claim": c["text"],
                     "quote": f"{c['file']}:{c['line']}", "implementation": impl, "tests": cov,
                     "execution": exe["status"], "contradictions": contra, "status": st, "why": why})
    alts = []
    for a in spec.get("alternatives", []):
        hit = probe(change, [{"path": "^src/", "added": a["added"]}])
        alts.append({"name": a["name"], "chosen": bool(hit), "evidence": hit[:1]})
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"stage": "tracer", "requirements_source": str(req_file.relative_to(FACTORY)), "curated_by": spec.get("curated_by"),
            "execution": exe, "tests_added": [{"name": t["name"], "file": t["file"], "line": t["line"]} for t in tests],
            "claims": rows, "alternatives": alts, "counts": counts}
