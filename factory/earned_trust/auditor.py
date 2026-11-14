"""Stage 3: Spec-Drift & Scope Auditor.

Deterministic first:
- scope: semantic hunks that no requirement explains (out of scope), and
  outlier snapshots whose residue a formatting-only out-of-scope change
  accounts for;
- drift: requirement contradictions (from the tracer) and added code or
  comments that contradict a checked fact (factory/knowledge/facts.json).

Its findings are accusations like the prosecutor's and go through the same
judge: nothing reaches the brief without a citation the judge confirmed.
"""

from __future__ import annotations

import json
import re

from .sources import FACTORY, Change

ESCAPES = re.compile(r"\\[rnt]|\s")


def formatting_only(hunk) -> bool:
    """The hunk only changes whitespace, in code or in string literals."""
    a = "".join(l.text for l in hunk.deleted)
    b = "".join(l.text for l in hunk.added)
    return bool(hunk.deleted) and a != b and ESCAPES.sub("", a) == ESCAPES.sub("", b)


def run(change: Change, classification: dict, trace: dict) -> dict:
    spec_file = FACTORY / "requirements" / f"{change.issue}.json"
    spec = json.loads(spec_file.read_text()) if spec_file.exists() else {}
    terms = spec.get("scope_terms", [])
    facts = json.loads((FACTORY / "knowledge" / "facts.json").read_text())["facts"]
    cats = {f["path"]: f for f in classification["files"]}
    findings = []

    out_of_scope = []
    for f in change.files:
        c = cats[f.path]
        if c["category"] not in ("semantic", "public-contract") or c.get("group_role") == "outlier":
            continue
        for h in f.hunks:
            changed = [l for l in h.lines if l.kind != " "]
            if not changed:
                continue
            text = "\n".join(l.text for l in changed)
            if any(t in text for t in terms):
                continue
            first = next((l for l in h.added), None) or changed[0]
            line = first.new_no or first.old_no
            fmt = formatting_only(h)
            out_of_scope.append({"file": f.path, "line": line, "formatting_only": fmt,
                                 "added": [l.text.strip() for l in h.added], "deleted": [l.text.strip() for l in h.deleted]})
            symbol = re.findall(r"[A-Za-z_]\w*", first.text)
            findings.append({
                "id": f"SCOPE-{sum(x['id'].startswith('SCOPE') for x in findings) + 1}", "source": "auditor (deterministic)", "category": "scope",
                "severity": "medium",
                "claim": ("Not part of the issue: nothing in the issue asks for this change."
                          + (" It only changes spacing." if fmt else "")),
                "file": f.path, "line_start": line, "line_end": line,
                "symbol": symbol[0] if symbol else first.text.strip()[:20],
            })

    # outliers explained by a formatting-only out-of-scope change
    fmt_changes = [o for o in out_of_scope if o["formatting_only"]]
    links = []
    for o in classification.get("outliers", []):
        if o["residue"]["whitespace_only"] and fmt_changes:
            src = fmt_changes[0]
            links.append({"outlier": o["path"], "explained_by": f"{src['file']}:{src['line']}",
                          "why": "the outlier's only change beyond the pattern is whitespace, and this out-of-scope hunk only changes whitespace in the generator's output"})

    for row in trace["claims"]:
        for c in row["contradictions"]:
            m = re.search(r"NETSTANDARD2_0|netstandard2\.0|NETFRAMEWORK|\.NET Framework", c["text"])
            sym = m.group(0) if m else re.findall(r"[A-Za-z_]\w*", c["text"])[0]
            findings.append({
                "id": f"DRIFT-{sum(x['id'].startswith('DRIFT') for x in findings) + 1}", "source": "auditor (deterministic)", "category": "spec-drift",
                "severity": "high",
                "claim": (f"Says something false: {next((x['short'] for x in facts if x['id'] == c.get('fact')), c['why'])}."
                          if row["id"].startswith("DOC") else f"Breaks the requirement \"{row['claim']}\": {c['why']}."),
                "requirement": row["id"],
                "file": c["file"], "line_start": c["line"], "line_end": c["line"], "symbol": sym,
                "fact": c.get("fact"),
            })
            break  # one citation per claim

    seen = {(x["file"], x["line_start"]) for x in findings}
    for f in change.files:
        for l in f.added_lines():
            for fact in facts:
                if re.search(fact["contradicted_by"], l.text) and (f.path, l.new_no) not in seen:
                    m = re.search(r"netstandard2\.0|NETSTANDARD2_0|\.NET Framework|NETFRAMEWORK", l.text)
                    findings.append({
                        "id": f"DRIFT-{sum(x['id'].startswith('DRIFT') for x in findings) + 1}", "source": "auditor (deterministic)", "category": "fact-contradiction",
                        "severity": "medium",
                        "claim": f"Says something false: {fact['short']}.",
                        "file": f.path, "line_start": l.new_no, "line_end": l.new_no,
                        "symbol": m.group(0) if m else l.text.strip()[:20], "fact": fact["id"],
                    })
    return {"stage": "auditor", "engine": "deterministic (scope terms + facts); LLM drift review is optional",
            "scope_terms": terms, "out_of_scope": out_of_scope, "outlier_links": links, "findings": findings}
