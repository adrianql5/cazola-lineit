"""Stage 4a: Adversarial Prosecutor.

Tries to break the change. Its accusations come from three places, each
labelled in the brief:
- rules: deterministic attack patterns over the diff (always on);
- llm: the configured model, asked for JSON accusations with file, line
  range and symbol (online, or from the replay cache);
- replay: the findings our own LLM-written concept draft invented before
  anyone read the branches, kept as a standing test of the judge.

Nothing here is trusted: every accusation goes to the judge.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import llm
from .sources import FACTORY, Change

PROMPT_VERSION = "prosecutor-v1"

SYSTEM = """You are the prosecutor in a code review of an AI-written change to MessagePack-CSharp.
Find ways the change is wrong, unsafe, or does more or less than its issue asks.
Answer ONLY with a JSON array. Each item: {"claim": str, "file": str, "line_start": int, "line_end": int,
"symbol": str (an identifier or token written on those lines), "severity": "low"|"medium"|"high",
"phantom_test": str (an xUnit test, as text, that would expose the problem) or null}.
Cite line numbers of the NEW file exactly as given (the number after L). Do not give confidence percentages.
If you find nothing, answer []."""


RULES = [
    {
        "id": "P-GLOBAL-WRAP",
        "added": r"this\.(?P<field>\w+)\s*=\s*.*=>\s*(?P<fn>\w+)\(",
        "severity": "high",
        "claim": "`{field}` is wrapped by `{fn}` for every caller, so whatever `{fn}` filters out is dropped for all "
                 "diagnostics, not only the ones the issue is about (e.g. a diagnostic of the compilation's own type "
                 "whose location is null or Location.None)",
        "symbol": "{fn}",
        "phantom": """[Fact]
public async Task DiagnosticWithoutSourceLocationFromOwnCompilationIsStillReported()
{{
    // A [MessagePackObject] declared in THIS compilation whose diagnostic has no syntax location
    // must still be reported after `{fn}` was introduced.
    // Arrange a type in the test source, trigger a diagnostic created with Location.None,
    // and assert it appears in the analyzer results.
}}""",
    },
    {
        "id": "P-FIRST-WINS",
        "added": r"if \(!(?P<dict>\w+)\.ContainsKey\(",
        "severity": "medium",
        "claim": "With duplicate keys the first member wins and the later one is dropped from the serialization model "
                 "silently; only the MsgPack005 error stops the build. This is the shared collection path, so it also "
                 "changes types that do get a generated formatter",
        "symbol": "ContainsKey",
        "phantom": """[Fact]
public async Task DuplicateKeyMemberIsNotSilentlyDroppedWhenDiagnosticIsSuppressed()
{{
    // With MsgPack005 suppressed via .editorconfig, a duplicate [Key(0)] must not produce
    // a formatter that silently omits the second member.
}}""",
    },
    {
        "id": "P-SILENT-SKIP",
        "added": r"^\s*continue;",
        "after": r"reportDiagnostic",
        "severity": "medium",
        "claim": "After reporting, the member is skipped with `continue`, so it is missing from the model; if the "
                 "diagnostic's severity is lowered by the user, the generated formatter silently leaves it out",
        "symbol": "continue",
        "phantom": None,
    },
    {
        "id": "P-TEST-EXCLUDED",
        "paths": r"\.csproj$",
        "added": r"Exclude=\"[^\"]*(?P<what>GeneratedFormatterFor\w+)",
        "severity": "high",
        "claim": "New execution tests are excluded from MapModeExecutionTests, so the new formatters are never run "
                 "in map mode: an evidence gap, not a pass",
        "symbol": "Exclude",
        "phantom": None,
    },
    {
        "id": "P-TFM-GUARD",
        "paths": r"\.tt$",
        "added": r"#if !NETSTANDARD2_0 && !NETFRAMEWORK",
        "severity": "high",
        "claim": "The guard compiles the attribute out for consumers targeting netstandard2.0 or .NET Framework, "
                 "although the attribute exists there (FACT-ECC-AVAILABILITY): those users keep the coverage skew the "
                 "issue asks to remove",
        "symbol": "NETSTANDARD2_0",
        "phantom": None,
    },
    {
        "id": "P-DOUBLE-RUN",
        "added": r"(?P<call>\w+Collector\.Collect)\(",
        "repeat": 2,
        "severity": "low",
        "claim": "`{call}` runs twice per formatter (once for the model with diagnostics off, once for the "
                 "diagnostics): double cost, and the two runs can disagree if one changes",
        "symbol": "{call}",
        "phantom": None,
    },
]


def rules(change: Change) -> list[dict]:
    out = []
    for r in RULES:
        for f in change.files:
            if "paths" in r and not re.search(r["paths"], f.path):
                continue
            if not f.path.endswith((".cs", ".tt", ".csproj")):
                continue
            hits = []
            for h in f.hunks:
                prev: list[str] = []
                for l in h.lines:
                    if l.kind == "+":
                        m = re.search(r["added"], l.text)
                        if m and ("after" not in r or any(re.search(r["after"], p) for p in prev[-3:])):
                            hits.append((l, m))
                    if l.kind != "-":
                        prev.append(l.text)
            if len(hits) < r.get("repeat", 1):
                continue
            l, m = hits[0]
            g = m.groupdict()
            out.append({
                "id": f"{r['id']}", "source": "rules (deterministic)", "category": "prosecution",
                "severity": r["severity"], "claim": r["claim"].format(**g),
                "file": f.path, "line_start": l.new_no, "line_end": l.new_no,
                "symbol": r["symbol"].format(**g),
                "phantom_test": r["phantom"].format(**g) if r["phantom"] else None,
                "also_at": [x.new_no for x, _ in hits[1:6]],
            })
            break  # one citation per rule and change
    return out


def replay(change: Change) -> list[dict]:
    d = json.loads((FACTORY / "knowledge" / "draft_hallucinations.json").read_text())
    return [{**a, "id": f"DRAFT-{i}", "source": "replay: our LLM-written concept draft", "category": "prosecution",
             "severity": "high", "phantom_test": None}
            for i, a in enumerate(d["accusations"], 1) if a["branch"] == change.branch]


def numbered(change: Change, classification: dict, limit: int = 60000) -> str:
    """The semantic part of the diff, with new-file line numbers, for the model."""
    keep = {f["path"] for f in classification["files"] if f["category"] in ("semantic", "public-contract", "test")}
    out = []
    for f in change.files:
        if f.path not in keep:
            continue
        out.append(f"### {f.path}")
        for h in f.hunks:
            for l in h.lines:
                n = l.new_no if l.new_no is not None else l.old_no
                out.append(f"L{n} {l.kind}{l.text}")
        if sum(len(x) for x in out) > limit:
            out.append("... (truncated)")
            break
    return "\n".join(out)


def ask_llm(change: Change, classification: dict, offline: bool) -> tuple[list[dict], dict]:
    user = (f"Issue #{change.issue}: {change.issue_title}\n\n{change.issue_body[:3000]}\n\n"
            f"Commit: {change.subject}\n\nDiff (semantic files only):\n{numbered(change, classification)}")
    cache = FACTORY / "cache" / change.branch / "llm"
    try:
        r = llm.chat(SYSTEM, user, prompt_version=PROMPT_VERSION, cache_dir=cache, offline=offline)
    except llm.LLMUnavailable as e:
        return [], {"status": "NOT RUN", "why": str(e)}
    try:
        items = llm.extract_json(r["content"])
    except ValueError as e:
        return [], {"status": "FAILED", "why": f"unparseable answer: {e}", "model": r["model"]}
    accs = []
    for i, a in enumerate(items if isinstance(items, list) else [], 1):
        accs.append({"id": f"LLM-{i}", "source": f"llm: {r['model']}", "category": "prosecution",
                     "severity": a.get("severity", "medium"), "claim": a.get("claim", ""), "file": a.get("file"),
                     "line_start": a.get("line_start"), "line_end": a.get("line_end"), "symbol": a.get("symbol"),
                     "phantom_test": a.get("phantom_test")})
    meta = {"status": "RAN", "model": r["model"], "prompt_version": r["prompt_version"],
            "input_sha256": r["input_sha256"], "cached": r["cached"], "accusations": len(accs)}
    return accs, meta


def run(change: Change, classification: dict, offline: bool, use_llm: bool = True) -> dict:
    accs = rules(change) + replay(change)
    meta = {"status": "NOT RUN", "why": "disabled for this run"}
    if use_llm:
        more, meta = ask_llm(change, classification, offline)
        accs += more
    return {"stage": "prosecutor", "llm": meta, "accusations": accs}
