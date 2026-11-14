"""Live measurements from this repository's pull requests, read from the
GitHub API: what share of each change a person had to read, which findings
were accepted or refuted (rules and AI apart), and how long it took from the
brief to the signature and to the merge.

Every review writes its numbers into the brief, hidden
(`<!-- sancho-metrics {...} -->`). A brief written before that existed
is read from its text, the PR's comments and the gate check instead.

    GITHUB_TOKEN=... python3 factory/sancho.py live [--repo owner/name]
"""

from __future__ import annotations

import json
import os
import re
import statistics
import time
from pathlib import Path

from . import github
from .sources import FACTORY

OUT = FACTORY / "bench" / "live.json"
AI_LABELS = FACTORY / "bench" / "ai_labels.json"
RULE_LABELS = FACTORY / "bench" / "labels.json"


def labels() -> dict:
    """Findings labelled real or false by a person reading the cited code:
    the AI's (ai_labels.json) and the rules' (labels.json)."""
    def precision(counts: dict) -> float | None:
        done = counts["real"] + counts["false_positive"]
        return round(counts["real"] / done, 3) if done else None
    ai = json.loads(AI_LABELS.read_text()) if AI_LABELS.exists() else {"findings": [], "labelled_by": ""}
    ai_counts = {"real": 0, "false_positive": 0, "unclear": 0}
    for f in ai["findings"]:
        ai_counts[f["label"]] += 1
    rules = json.loads(RULE_LABELS.read_text()) if RULE_LABELS.exists() else {"labels": {}, "labelled_by": ""}
    rule_counts = {"real": 0, "false_positive": 0, "unclear": 0}
    for per_branch in rules["labels"].values():
        for lab in per_branch.values():
            rule_counts[lab["label"] if lab["label"] in rule_counts else "unclear"] += 1
    return {"ai": {**ai_counts, "precision": precision(ai_counts), "findings": ai["findings"],
                   "labelled_by": ai.get("labelled_by", ""), "model": ai.get("model", "")},
            "rules": {**rule_counts, "precision": precision(rule_counts), "labelled_by": rules.get("labelled_by", "")}}
CMD = re.compile(r"^/(accept|refute)\s+(\S+)", re.I)


def ts(s: str | None) -> float | None:
    return time.mktime(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ")) if s else None


def minutes(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    return round((ts(b) - ts(a)) / 60, 1)


def from_text(repo: str, pr: dict, brief: dict) -> dict:
    """Metrics of a brief written before the hidden block existed."""
    body = brief["body"]
    m = re.search(r"read \*\*([\d,]+)\*\* of ([\d,]+) lines", body)
    full = re.search(r"full read needed \(([\d,]+) lines\)", body)
    if m:
        must, total = int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))
    elif full:
        total = int(full.group(1).replace(",", ""))
        every = re.search(r"\*\*Read:\*\* everything \(([\d,]+) lines\)", body)
        must = int(every.group(1).replace(",", "")) if every else total
    else:
        must = total = 0
    ids = re.findall(r"^\*\*([A-Z][A-Z0-9]*-[A-Z0-9-]+)\*\* · `", body, re.M)
    sha = pr["head"]["sha"]
    commit_at = github.gh("GET", f"/repos/{repo}/commits/{sha}")["commit"]["committer"]["date"]
    answers = {}
    for c in sorted(github.all_comments(repo, pr["number"]) + github.review_comments(repo, pr["number"]),
                    key=lambda c: c["created_at"]):
        if c["user"]["type"] == "Bot" or c["created_at"] < commit_at or c["author_association"] not in github.SIGNERS:
            continue
        for line in (c.get("body") or "").splitlines():
            mm = CMD.match(line.strip())
            if mm and mm.group(2) in ids:
                verdict = "accepted" if mm.group(1).lower() == "accept" else "refuted"
                answers[mm.group(2)] = {"id": mm.group(2), "verdict": verdict, "by": c["user"]["login"],
                                        "at": c["created_at"], "source": "ai" if mm.group(2).startswith("LLM") else "rules"}
    checks = [c for name in (github.CHECK, github.OLD_CHECK)
              for c in github.gh("GET", f"/repos/{repo}/commits/{sha}/check-runs?check_name={name}").get("check_runs", [])]
    done = next((c for c in checks if c.get("conclusion") == "success"), None)
    return {"v": 0, "pr": pr["number"], "title": pr["title"], "sha": sha, "pr_opened_at": pr["created_at"],
            "brief_published_at": max(brief["created_at"], commit_at), "tier": "T2" if full else ("T1" if m else "?"),
            "lines_total": total, "lines_must_read": must,
            "findings": [{"id": i, "source": "ai" if i.startswith("LLM") else "rules"} for i in ids],
            "answers": list(answers.values()), "gate": "success" if done else "action_required",
            "signed_at": done["completed_at"] if done else None, "signers": []}


def collect(repo: str) -> dict:
    rows = []
    page = 1
    while True:
        prs = github.gh("GET", f"/repos/{repo}/pulls?state=all&per_page=100&page={page}")
        for pr in prs:
            comments = github.all_comments(repo, pr["number"])
            brief = next((c for c in comments if github.MARK in (c.get("body") or "")), None)
            if not brief:
                continue  # not reviewed by the factory
            m = github.METRICS.search(brief["body"])
            row = json.loads(m.group(1)) if m else from_text(repo, pr, brief)
            row.update({"merged_at": pr.get("merged_at"), "state": pr["state"], "url": pr["html_url"]})
            row["minutes_to_sign"] = minutes(row.get("brief_published_at"), row.get("signed_at"))
            row["minutes_to_merge"] = minutes(row.get("pr_opened_at"), row.get("merged_at"))
            rows.append(row)
        if len(prs) < 100:
            break
        page += 1
    rows.sort(key=lambda r: r["pr"])
    lab = labels()
    by_key = {(f["pr"], f["id"], f["sha"]): f for f in lab["ai"]["findings"]}
    for r in rows:
        for f in r["findings"]:
            hit = by_key.get((r["pr"], f["id"], r["sha"][:12]))
            if hit:
                f["label"] = hit["label"]

    answers = {"rules": {"accepted": 0, "refuted": 0, "open": 0}, "ai": {"accepted": 0, "refuted": 0, "open": 0}}
    for r in rows:
        answered = {a["id"]: a for a in r["answers"]}
        for f in r["findings"]:
            a = answered.get(f["id"])
            answers[f["source"]]["open" if not a else a["verdict"]] += 1
    for v in answers.values():
        done = v["accepted"] + v["refuted"]
        v["acceptance_rate"] = round(v["accepted"] / done, 3) if done else None

    signed = [r["minutes_to_sign"] for r in rows if r["minutes_to_sign"] is not None]
    merged = [r["minutes_to_merge"] for r in rows if r["minutes_to_merge"] is not None]
    total = sum(r["lines_total"] for r in rows)
    must = sum(r["lines_must_read"] for r in rows)
    _, events = github.load_trust_events(repo)
    return {
        "source": f"GitHub API, pull requests of {repo}",
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "prs": rows,
        "summary": {
            "reviewed": len(rows), "signed": len(signed), "merged": len(merged),
            "lines_total": total, "lines_to_humans": must,
            "share_lines_to_humans": round(must / total, 3) if total else None,
            "median_minutes_to_sign": statistics.median(signed) if signed else None,
            "median_minutes_to_merge": statistics.median(merged) if merged else None,
            "answers": answers,
            "escapes": len(events),
        },
        "labels": lab,
    }


def main(repo: str | None = None) -> dict:
    repo = repo or os.environ.get("GITHUB_REPOSITORY")
    if not repo or not os.environ.get("GITHUB_TOKEN"):
        raise SystemExit("Set GITHUB_TOKEN (and GITHUB_REPOSITORY, or pass --repo owner/name) to read the pull requests.")
    data = collect(repo)
    OUT.write_text(json.dumps(data, indent=1))
    s = data["summary"]
    print(f"{s['reviewed']} PRs reviewed, {s['signed']} signed, {s['lines_to_humans']:,} of {s['lines_total']:,} lines "
          f"to people · rules {s['answers']['rules']} · AI {s['answers']['ai']} → {Path(OUT).relative_to(FACTORY.parent)}")
    return data
