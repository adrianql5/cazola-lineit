"""The Trust Ledger: how far each module of the codebase has earned summary
review, from upstream history, plus a SQLite record of every run, finding,
human command, LLM call and receipt.

Heuristic (its limits: it reads commit subjects, so a revert or a fix not
called that is invisible to it):
- a module is a directory, at most three levels deep;
- window: the commits of the last 730 days of the cached master history;
- REVOKED: a commit whose subject says "revert" touched it in the window,
  or at least half of its commits are fixes that follow another change to it
  within 30 days (with 4 or more commits);
- EARNED: 5 or more commits in the window, no revert, under a quarter fixes;
- PROBATION: everything else (too little history to say either way).
A module that lets a seeded defect escape is demoted one level by the
guardrail (bench), whatever its history says.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath

from . import config
from .sources import FACTORY

ROOT = FACTORY.parent
HISTORY = FACTORY / "cache" / "upstream_history.json"
REVERT_RE = re.compile(r"\brevert", re.I)
FIX_RE = re.compile(r"\b(fix(es|ed)?|bug|regression|hotfix)\b", re.I)
WINDOW_DAYS = 730
DEMOTE = {"EARNED": "PROBATION", "PROBATION": "REVOKED", "REVOKED": "REVOKED"}

# What the factory has learned on this repository: spot-check escapes. Filled
# from the repo's trust-ledger issue in GitHub Actions, or from
# ledger/trust-events.json locally.
EVENTS: list[dict] = []
LOCAL_EVENTS = ROOT / "ledger" / "trust-events.json"


def events() -> list[dict]:
    out = list(EVENTS)
    if not out and LOCAL_EVENTS.exists():
        out = json.loads(LOCAL_EVENTS.read_text())
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return [e for e in out if e.get("until", "9999") >= today]


def record_local(event: dict) -> None:
    LOCAL_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(LOCAL_EVENTS.read_text()) if LOCAL_EVENTS.exists() else []
    LOCAL_EVENTS.write_text(json.dumps(old + [event], indent=1))


def module_of(path: str) -> str:
    parts = PurePosixPath(path).parts[:-1]
    return "/".join(parts[:3]) or "."


def trust_table() -> dict:
    h = json.loads(HISTORY.read_text())
    if not config.upstream_history():  # another repository: its own spot-checks only
        h = {"source": "none: the only history here is MessagePack-CSharp's, and this is another repository",
             "commits": []}
    commits = h["commits"]
    for c in commits:
        c["dt"] = datetime.fromisoformat(c["date"])
    latest = max((c["dt"] for c in commits), default=datetime.now().astimezone())
    window = [c for c in commits if c["dt"] >= latest - timedelta(days=WINDOW_DAYS)]
    per: dict[str, list[dict]] = defaultdict(list)
    for c in sorted(window, key=lambda c: c["dt"]):
        for m in {module_of(f) for f in c["files"]}:
            per[m].append(c)
    table = {}
    for m, cs in per.items():
        reverts = [c for c in cs if REVERT_RE.search(c["subject"])]
        fixes = []
        for i, c in enumerate(cs):
            if FIX_RE.search(c["subject"]) and i > 0 and c["dt"] - cs[i - 1]["dt"] <= timedelta(days=30):
                fixes.append(c)
        n = len(cs)
        ratio = len(fixes) / n if n else 0
        if reverts or (n >= 4 and ratio >= 0.5):
            state = "REVOKED"
        elif n >= 5 and ratio < 0.25:
            state = "EARNED"
        else:
            state = "PROBATION"
        table[m] = {"state": state, "commits": n, "reverts": len(reverts), "fix_followups": len(fixes),
                    "fix_ratio": round(ratio, 2),
                    "evidence": [f"{c['sha'][:10]} {c['subject'][:70]}" for c in (reverts + fixes)[:3]]}
    for e in events():
        for m in e.get("modules", []):
            row = table.setdefault(m, {"state": "PROBATION", "commits": 0, "reverts": 0, "fix_followups": 0,
                                       "fix_ratio": 0, "evidence": []})
            row["state"] = DEMOTE[row["state"]]
            row.setdefault("lowered_by", []).append(f"spot-check escape on PR #{e.get('pr')} ({e.get('at', '')[:10]})")
    return {"source": h["source"], "window": f"{WINDOW_DAYS} days up to {latest.date()}",
            "commits_in_window": len(window), "modules": table}


def states_for(paths: list[str], table: dict) -> dict[str, dict]:
    out = {}
    for p in paths:
        m = module_of(p)
        while m not in table["modules"] and "/" in m:
            m = m.rsplit("/", 1)[0]
        out[p] = {"module": m, **table["modules"].get(m, {"state": "PROBATION", "commits": 0, "reverts": 0,
                                                            "fix_followups": 0, "fix_ratio": 0, "evidence": []})}
    return out


# --- the SQLite ledger -------------------------------------------------------

SCHEMA = """
create table if not exists runs (id integer primary key, branch text, sha text, diff_sha text, tier text,
    brief_sha text, started text, mode text);
create table if not exists findings (run_id integer, finding_id text, source text, verdict text, file text,
    line integer, symbol text, claim text);
create table if not exists events (run_id integer, at text, actor text, command text, args text, simulated integer);
create table if not exists llm_calls (run_id integer, stage text, model text, prompt_version text,
    input_sha256 text, cached integer, status text);
create table if not exists receipts (run_id integer, hash text, owner text, signed_at text, path text);
"""


def db(path: Path | None = None) -> sqlite3.Connection:
    path = path or ROOT / "ledger" / "ledger.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
