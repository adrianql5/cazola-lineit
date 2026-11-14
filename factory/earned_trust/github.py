"""The factory in GitHub Actions: it runs by itself on every pull request.

On `pull_request`: review the PR's diff, run the tests it adds (`dotnet
test`), post the Evidence Brief as one comment (updated in place), and open
the check run `earned-trust/human-accountability-gate` as action_required.

On `issue_comment` (a PR comment): review again and replay every slash
command written on the PR since its last commit, in order. Nothing is stored
between runs: the PR's comments are the state, and GitHub says who wrote
each one. When the gate is met the check turns green with the receipt in
its output, and the receipt is uploaded as an artifact.

Only OWNER, MEMBER or COLLABORATOR comments can /sign (GitHub's
author_association). A new commit starts a new gate: commands written
before it are ignored.

    python3 factory/et.py github --target target/   (inside the workflow)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
import urllib.request
from pathlib import Path

from . import brief, commands, llm, pipeline, receipt, sources, tracer, worker
from .sources import FACTORY

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
CHECK = "earned-trust/human-accountability-gate"
MARK = "<!-- earned-trust-brief -->"
EVIDENCE = re.compile(r"<!-- earned-trust-evidence (.*?) -->", re.S)
SIGNERS = {"OWNER", "MEMBER", "COLLABORATOR"}


def gh(method: str, path: str, body: dict | None = None, accept: str = "application/vnd.github+json"):
    req = urllib.request.Request(path if path.startswith("http") else API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    req.add_header("Accept", accept)
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data.decode() if accept.endswith("diff") else (json.loads(data) if data else {})


def all_comments(repo: str, number: int) -> list[dict]:
    out, page = [], 1
    while True:
        batch = gh("GET", f"/repos/{repo}/issues/{number}/comments?per_page=100&page={page}")
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def issue_number(pr: dict) -> int:
    for text in (pr["head"]["ref"], pr["title"], pr.get("body") or ""):
        m = re.search(r"issue-(\d+)|#(\d+)", text)
        if m:
            return int(m.group(1) or m.group(2))
    return 0


def issue_text(n: int) -> dict:
    """From the replay cache if we have it, else from the upstream repository."""
    for d in (FACTORY / "cache").glob("*/issue.json"):
        i = json.loads(d.read_text())
        if i.get("number") == n:
            return {"title": i["title"], "body": i.get("body") or "", "url": i.get("url", "")}
    upstream = os.environ.get("ET_ISSUE_REPO", "MessagePack-CSharp/MessagePack-CSharp")
    try:
        i = gh("GET", f"/repos/{upstream}/issues/{n}")
        return {"title": i["title"], "body": i.get("body") or "", "url": i["html_url"]}
    except Exception:
        return {"title": "", "body": "", "url": ""}


def ts(s: str) -> float:
    return time.mktime(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))


def evidence(change: sources.Change, run_dir: Path, target: Path | None, old_body: str) -> dict | None:
    """Run the tests the change adds; on comment events, reuse the result
    stored (hidden) in the brief comment for the same commit."""
    if target is None:
        m = EVIDENCE.search(old_body or "")
        if m:
            ev = json.loads(m.group(1))
            if ev.get("sha") == change.sha:
                return ev
        return None
    facts = json.loads((FACTORY / "knowledge" / "facts.json").read_text())["facts"]
    added = tracer.run(change, run_dir, facts)["tests_added"]
    res = worker.execute(target, added, change.sha)
    codes = {e for p in res.get("per_project", []) for e in p["errors"]} | set(res.get("warnings", []))
    if res["status"] == "ERROR" and "CS9057" in codes:
        # the pinned SDK's compiler is older than the generator needs: retry on the newer SDK, and say so
        res = worker.execute(target, added, change.sha, ignore_global_json=True)
    return res


def main(target: str | None) -> int:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    name = os.environ["GITHUB_EVENT_NAME"]
    repo = os.environ["GITHUB_REPOSITORY"]
    if name == "issue_comment":
        if "pull_request" not in event["issue"]:
            print("not a pull request comment")
            return 0
        if not any(l.strip().startswith("/") for l in (event["comment"]["body"] or "").splitlines()):
            print("no slash command in the comment")
            return 0
        pr = gh("GET", f"/repos/{repo}/pulls/{event['issue']['number']}")
        target = None  # tests ran on the pull_request event; reuse that result
    else:
        pr = event["pull_request"]
    number, sha = pr["number"], pr["head"]["sha"]

    diff = gh("GET", f"/repos/{repo}/pulls/{number}", accept="application/vnd.github.v3.diff")
    n = issue_number(pr)
    meta = {"issue": n, "sha": sha, "subject": pr["title"], "author": pr["user"]["login"]}
    change = sources.make(f"pr-{number}", meta, issue_text(n), diff, f"GitHub {repo}#{number}")
    run_dir = pipeline.RUNS / f"pr-{number}"
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)

    comments = all_comments(repo, number)
    mine = next((c for c in comments if MARK in (c.get("body") or "")), None)
    ev = evidence(change, run_dir, Path(target).resolve() if target else None, mine["body"] if mine else "")
    if ev:
        (run_dir / "tests.json").write_text(json.dumps(ev, indent=1))

    report = pipeline.review(change, offline=not llm.configured(), run_dir=run_dir)

    # Replay the PR's slash commands written since its last commit.
    commit_at = gh("GET", f"/repos/{repo}/commits/{sha}")["commit"]["committer"]["date"]
    st = commands.load(run_dir)
    st["published_at"] = max(mine["created_at"], commit_at) if mine else commit_at
    commands.save(run_dir, st)
    log = []
    for c in sorted(comments, key=lambda c: c["created_at"]):
        if c["user"]["type"] == "Bot" or MARK in (c.get("body") or ""):
            continue
        lines = [l.strip() for l in (c["body"] or "").splitlines() if l.strip().startswith("/")]
        if not lines:
            continue
        if ts(c["created_at"]) < ts(commit_at):
            log.append(f"- @{c['user']['login']}: ignored, written before the last commit")
            continue
        for l in lines:
            ok = c["author_association"] in SIGNERS
            _, reply = commands.apply(report, run_dir, c["user"]["login"], l, at=c["created_at"], can_sign=ok)
            log.append(f"- @{c['user']['login']} `{l[:70]}` → {reply}")
    state = commands.load(run_dir)
    gate = commands.gate(report, state)

    hidden = f"<!-- earned-trust-evidence {json.dumps({k: v for k, v in ev.items() if k != 'log_tail'})} -->" if ev else ""
    text = brief.render(report, state)
    if log:
        text += "\n<details open><summary><b>Commands on this PR</b></summary>\n\n" + "\n".join(log[-30:]) + "\n\n</details>\n"
    body = f"{MARK}\n{hidden}\n{text}"
    if mine:
        gh("PATCH", f"/repos/{repo}/issues/comments/{mine['id']}", {"body": body})
    else:
        gh("POST", f"/repos/{repo}/issues/{number}/comments", {"body": body})

    out = {"title": f"{report['router']['tier']}: " + ("signed" if gate["conclusion"] == "success" else "; ".join(gate["missing"]))[:200],
           "summary": "\n".join(brief.story(report))}
    summary_md = text
    if gate["conclusion"] == "success":
        rc_md = (run_dir / "receipt.md").read_text()
        out["text"] = rc_md[:60000]
        summary_md = rc_md + "\n\n" + text
    gh("POST", f"/repos/{repo}/check-runs", {"name": CHECK, "head_sha": sha, "status": "completed",
                                            "conclusion": gate["conclusion"], "details_url": pr["html_url"], "output": out})
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(summary_md)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"run_dir={run_dir}\ngate={gate['conclusion']}\ntier={report['router']['tier']}\n")
    print(f"PR #{number}: {report['router']['tier']}, gate {gate['conclusion']}"
          + (f" ({'; '.join(gate['missing'])})" if gate["missing"] else ""))
    return 0
