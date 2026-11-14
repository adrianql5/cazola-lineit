"""Stage 1: Classifier. Deterministic, no LLM.

Puts every file in mechanical / semantic / public-contract / test / docs,
groups mechanical files by the normalized shape of their hunks so the one
that does not fit the pattern stands out, and raises the T2 triggers.

Engine: diff heuristics and regexes. A Roslyn classifier
(tools/EarnedTrust.Classifier) is P2 and is not used; the brief says so.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath

from .gitdiff import FileDiff
from .sources import Change

ENGINE = "heuristic: diff shape + text within each shape + regex rules (Roslyn classifier not used)"

SNAPSHOT_RE = re.compile(r"^tests/.*/Resources/.*\.g\.cs$")

CS_KEYWORDS = set("""
abstract as base bool break byte case catch char checked class const continue decimal default delegate do
double else enum event explicit extern false finally fixed float for foreach goto if implicit in int interface
internal is lock long namespace new null object operator out override params private protected public readonly
ref return sbyte sealed short sizeof stackalloc static string struct switch this throw true try typeof uint ulong
unchecked unsafe ushort using virtual void volatile while partial record global where get set init var
endif elif define undef region endregion pragma
""".split())


@dataclass(frozen=True)
class Rule:
    id: str
    why: str
    paths: str
    added: str


# Each one forces T2: a human reads the whole change, whatever else it is.
T2_RULES = [
    Rule("T2-PUBLIC-API", "new public type or member in a published package (MessagePack, MessagePack.Annotations)",
         r"^src/MessagePack(\.Annotations)?/", r"^\s*public\s+(?!override\b)"),
    Rule("T2-ANALYZER-SEVERITY", "new or changed analyzer rule severity: it can break users' builds",
         r"AnalyzerReleases\.(Un)?[Ss]hipped\.md$", r"\|\s*(Error|Warning|Info)\s*\|"),
    Rule("T2-ANALYZER-SEVERITY", "new or changed analyzer rule severity: it can break users' builds",
         r"^src/", r"DiagnosticSeverity\.Error"),
    Rule("T2-TEST-EXCLUSION", "tests excluded from a test project: evidence that silently stops running",
         r"^tests/.*\.csproj$", r"Exclude=|Remove="),
    Rule("T2-UNSAFE", "unsafe code, Marshal or Reflection.Emit",
         r"^src/", r"\bunsafe\b|\bMarshal\.|Reflection\.Emit|\bDynamicMethod\b|\bILGenerator\b"),
    Rule("T2-SERIALIZATION-CONTRACT", "changes how members map to the wire format by default",
         r"^src/", r"(?i)contractless|wire contract|using its name as a string key"),
]


def normalize(text: str) -> str:
    """A line's shape: no spaces, no identifiers, no literals."""
    t = text.strip()
    t = re.sub(r'"(?:\\.|[^"\\])*"', '"S"', t)
    t = re.sub(r"\b\d+\b", "N", t)
    t = re.sub(r"[A-Za-z_][A-Za-z0-9_]*", lambda m: m.group(0) if m.group(0) in CS_KEYWORDS else "ID", t)
    return re.sub(r"\s+", "", t)


def hunk_signature(h) -> tuple[str, ...]:
    return tuple(l.kind + normalize(l.text) for l in h.lines if l.kind != " ")


def file_shape(f: FileDiff) -> tuple[tuple[str, ...], ...]:
    return tuple(sorted(set(hunk_signature(h) for h in f.hunks)))


def t4_twin(f: FileDiff, paths: set[str]) -> str | None:
    p = PurePosixPath(f.path)
    if p.suffix != ".cs":
        return None
    tt = str(p.with_suffix(".tt"))
    return tt if tt in paths else None


T4_BOILERPLATE = {"this", "Write", "ToStringHelper", "ToStringWithCulture", "r", "n", "t", "rn", "nt", "tt"}


def t4_consistent(cs: FileDiff, tt: FileDiff) -> tuple[bool, list[str]]:
    """Every identifier the generated .cs adds must come from its template's
    added lines; one that doesn't means the .cs was edited by hand."""
    # what the template change shows (added and context lines), plus what the
    # .cs already had on the lines it rewrites
    tt_text = " ".join(l.text for h in tt.hunks for l in h.lines if l.kind != "-")
    tt_text += " " + " ".join(l.text for l in cs.deleted_lines())
    tt_words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", tt_text))
    stray = []
    for l in cs.added_lines():
        for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", l.text):
            if w not in tt_words and w not in T4_BOILERPLATE:
                stray.append(f"{cs.path}:{l.new_no}: `{w}`")
    return not stray, stray


def category(f: FileDiff, paths: set[str], files: dict[str, FileDiff]) -> tuple[str, str]:
    p = f.path
    if re.search(r"AnalyzerReleases\.", p):
        return "public-contract", "analyzer release notes: the shipped rule list and severities"
    if p.endswith(".md") or p.startswith("doc/"):
        return "docs", "documentation"
    if SNAPSHOT_RE.match(p):
        return "mechanical", "generated test snapshot (.g.cs under tests/**/Resources)"
    if p.startswith("tests/") and p.endswith(".csproj"):
        return "test", "test project file"
    if p.startswith("tests/"):
        return "test", "test code"
    tt = t4_twin(f, paths)
    if tt:
        ok, stray = t4_consistent(f, files[tt])
        if ok:
            return "mechanical", f"T4 output of {tt} (in this diff, read by a human); every added identifier comes from it"
        return "semantic", f"generated from {tt}, but adds identifiers its template does not: {', '.join(stray[:3])}"
    for r in T2_RULES:
        if r.id == "T2-PUBLIC-API" and re.search(r.paths, p) and any(re.search(r.added, l.text) for l in f.added_lines()):
            return "public-contract", r.why
    return "semantic", "source code"


def residue(f: FileDiff, pattern: set[str]) -> dict:
    """What an outlier changes beyond the dominant pattern, and whether that
    is only whitespace (a formatting change) or real code."""
    added = [l for l in f.added_lines() if l.kind + normalize(l.text) not in pattern]
    deleted = f.deleted_lines()
    squash = lambda ls: re.sub(r"\s+", "", "".join(l.text for l in ls))
    return {
        "added": [{"line": l.new_no, "text": l.text} for l in added],
        "deleted": [{"line": l.old_no, "text": l.text} for l in deleted],
        "whitespace_only": squash(added) == squash(deleted),
    }


def triggers(change: Change) -> list[dict]:
    out = []
    for f in change.files:
        for r in T2_RULES:
            if not re.search(r.paths, f.path):
                continue
            for l in f.added_lines():
                if re.search(r.added, l.text):
                    out.append({"rule": r.id, "why": r.why, "file": f.path, "line": l.new_no, "text": l.text.strip()[:160]})
                    break  # one citation per rule and file is enough
    return out


def content(f: FileDiff) -> tuple[str, ...]:
    """A file's changed lines as written (only surrounding spaces dropped)."""
    return tuple(sorted({l.kind + l.text.strip() for h in f.hunks for l in h.lines if l.kind != " "}))


def run(change: Change, content_check: bool = True) -> dict:
    paths = {f.path for f in change.files}
    by_path = {f.path: f for f in change.files}
    files = []
    for f in change.files:
        cat, why = category(f, paths, by_path)
        files.append({"path": f.path, "category": cat, "reason": why, "added": f.added, "deleted": f.deleted, "status": f.status})

    # Pattern detection over the snapshots: group by shape, flag what doesn't fit.
    snaps = [by_path[x["path"]] for x in files if x["category"] == "mechanical" and SNAPSHOT_RE.match(x["path"])]
    groups: dict[tuple, list[FileDiff]] = defaultdict(list)
    for f in snaps:
        groups[file_shape(f)].append(f)
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[1][0].path))
    group_out, outliers = [], []
    n = len(snaps)
    threshold = max(2, round(0.05 * n))  # a shape shared by fewer files than this is an outlier
    dominant_lines: set[str] = set()
    for i, (shape, members) in enumerate(ordered):
        # a pattern needs peers: a shape fewer files share than the threshold is
        # an outlier even when it is the biggest one (a lone snapshot has no pattern)
        if len(members) < threshold:
            role = "outlier"
        else:
            role = "dominant" if i == 0 else "secondary"
        if i == 0:
            dominant_lines = {s for sig in shape for s in sig}
        preview = sorted({s for sig in shape for s in sig})
        gid = f"G{i + 1}"
        group_out.append({"id": gid, "role": role, "size": len(members), "shape": preview,
                          "files": [m.path for m in members][:5] + (["..."] if len(members) > 5 else [])})
        for m in members:
            for x in files:
                if x["path"] == m.path:
                    x["group"] = gid
                    x["group_role"] = role
            if role == "outlier":
                outliers.append({"path": m.path, "group": gid, "added": m.added, "deleted": m.deleted,
                                 "why": f"its hunks have a shape only {len(members)} of {n} snapshots share",
                                 "residue": residue(m, dominant_lines)})
        # Same shape, different words: `[ExcludeFromCodeCoverage]` swapped for
        # another attribute keeps the shape, so check the text inside a pattern too.
        if content_check and role != "outlier" and len(members) >= threshold:
            variants: dict[tuple, list[FileDiff]] = defaultdict(list)
            for m in members:
                variants[content(m)].append(m)
            for v, ms in variants.items():
                if len(ms) < threshold and len(variants) > 1:
                    for m in ms:
                        for x in files:
                            if x["path"] == m.path:
                                x["group_role"] = "outlier"
                        outliers.append({"path": m.path, "group": gid, "added": m.added, "deleted": m.deleted,
                                         "why": f"same shape as {gid}, but its text is shared by only {len(ms)} of {len(members)} files in it",
                                         "residue": residue(m, set()) | {"whitespace_only": False}})
    for x in files:
        if x.get("group_role") == "outlier":
            x["category"] = "semantic"
            x["reason"] = "snapshot that does not fit the pattern of the others (outlier): read by a human"

    trig = triggers(change)
    count = defaultdict(int)
    for x in files:
        count[x["category"]] += 1
    return {
        "stage": "classifier",
        "engine": ENGINE,
        "files": files,
        "counts": dict(count),
        "snapshots": n,
        "groups": group_out,
        "outlier_threshold": threshold,
        "content_check": content_check,
        "outliers": outliers,
        "triggers": trig,
    }
