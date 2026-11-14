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
import shlex
import shutil
import time
import urllib.request
from pathlib import Path

from . import brief, commands, ledger, llm, pipeline, sources, tracer, worker
from .sources import FACTORY

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
CHECK = "earned-trust/human-accountability-gate"
MARK = "<!-- earned-trust-brief -->"
EVIDENCE = re.compile(r"<!-- earned-trust-evidence (.*?) -->", re.S)
LLM_ANSWERS = re.compile(r"<!-- earned-trust-llm (.*?) -->", re.S)
METRICS = re.compile(r"<!-- earned-trust-metrics (.*?) -->", re.S)


def finding_source(f: dict) -> str:
    """Who raised a finding: the AI, or a deterministic rule (also when the AI raised it too)."""
    return "ai" if f["source"].startswith("llm") else "rules"


def metrics(pr: dict, sha: str, report: dict, state: dict, gate: dict) -> dict:
    """What the live dashboard needs from this review, kept hidden in the brief."""
    rd = report["router"]["read"]
    src = {f["id"]: finding_source(f) for f in report["judge"]["accepted"]}
    signs = [e for e in state["events"] if e["command"].lower().startswith("/sign")]
    return {
        "v": 1, "pr": pr["number"], "title": pr["title"], "sha": sha, "pr_opened_at": pr.get("created_at"),
        "brief_published_at": state["published_at"], "tier": report["router"]["tier"],
        "lines_total": rd["lines_total"], "lines_must_read": rd["lines_must_read"],
        "files_total": rd["files_total"], "files_must_read": rd["files_must_read"],
        "findings": [{"id": i, "source": s} for i, s in src.items()],
        "answers": [{"id": i, "verdict": v["verdict"], "by": v["by"], "at": v["at"], "source": src.get(i, "rules")}
                    for i, v in state["findings"].items()],
        "decisions": [{"id": i, "option": d["option"], "by": d["by"], "at": d["at"]} for i, d in state["decisions"].items()],
        "abstentions": len(report["abstentions"]), "gate": gate["conclusion"],
        "signed_at": signs[-1]["at"] if gate["conclusion"] == "success" and signs else None,
        "signers": [x["by"] for x in state["signatures"]],
        "llm": report["prosecutor"]["llm"].get("model") if report["prosecutor"]["llm"]["status"] == "RAN" else None,
        "tests": report["tracer"]["execution"]["status"],
    }


def restore_llm(old_body: str, sha: str, cache: Path) -> None:
    """Comment runs reuse the LLM answers of the pull_request run for the same
    commit: the same findings, no new cost."""
    m = LLM_ANSWERS.search(old_body or "")
    if not m:
        return
    saved = json.loads(m.group(1))
    if saved.get("sha") != sha:
        return
    cache.mkdir(parents=True, exist_ok=True)
    for name, record in saved["answers"].items():
        (cache / name).write_text(json.dumps(record))


def save_llm(cache: Path, sha: str) -> str:
    if not cache.exists():
        return ""
    answers = {p.name: json.loads(p.read_text()) for p in sorted(cache.glob("*.json"))}
    return f"<!-- earned-trust-llm {json.dumps({'sha': sha, 'answers': answers}).replace('--', '- -')} -->" if answers else ""
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


def issue_text(n: int, repo: str) -> dict:
    """From the replay cache if we have it, else from the upstream repository."""
    for d in (FACTORY / "cache").glob("*/issue.json"):
        i = json.loads(d.read_text())
        if i.get("number") == n:
            return {"title": i["title"], "body": i.get("body") or "", "url": i.get("url", "")}
    if not n:
        return {"title": "", "body": "", "url": ""}
    upstream = os.environ.get("ET_ISSUE_REPO") or repo
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


LEDGER_MARK = "<!-- earned-trust-ledger -->"
FINDING_MARK = "<!-- earned-trust-finding {id} {sha} -->"


def profile_name(login: str, seen: dict[str, str | None]) -> str | None:
    """The name on LOGIN's GitHub profile, or None when it has none."""
    if login not in seen:
        try:
            seen[login] = (gh("GET", f"/users/{login}").get("name") or "").strip() or None
        except OSError:
            seen[login] = None
    return seen[login]


def with_name(line: str, login: str, seen: dict[str, str | None]) -> str | None:
    """A bare `/sign` signs with the name on the GitHub profile. None when the
    profile has no name, so the signer must write it."""
    if line.strip().lower() != "/sign":
        return line
    name = profile_name(login, seen)
    return f"/sign {shlex.quote(name)}" if name else None


def review_comments(repo: str, number: int) -> list[dict]:
    out, page = [], 1
    while True:
        batch = gh("GET", f"/repos/{repo}/pulls/{number}/comments?per_page=100&page={page}")
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def ledger_issue(repo: str) -> dict | None:
    for page in (1, 2, 3):
        for i in gh("GET", f"/repos/{repo}/issues?state=all&per_page=100&page={page}"):
            if LEDGER_MARK in (i.get("body") or ""):
                return i
    return None


def load_trust_events(repo: str) -> tuple[dict | None, list[dict]]:
    i = ledger_issue(repo)
    if not i:
        return None, []
    m = re.search(r"```json\n(.*?)\n```", i["body"], re.S)
    return i, (json.loads(m.group(1)) if m else [])


def save_trust_event(repo: str, issue: dict | None, events: list[dict], new: dict) -> None:
    events = events + [new]
    body = (f"{LEDGER_MARK}\nThe Earned-Trust factory keeps here what it has learned about this repository. "
            "When a spot-check finds a problem the pattern check missed, the folders involved lose a level of "
            "trust for 90 days, so their files are read in full again. Edit with care.\n\n"
            f"```json\n{json.dumps(events, indent=1)}\n```\n")
    if issue:
        gh("PATCH", f"/repos/{repo}/issues/{issue['number']}", {"body": body})
        num = issue["number"]
    else:
        num = gh("POST", f"/repos/{repo}/issues", {"title": "Earned-Trust trust ledger", "body": body})["number"]
    gh("POST", f"/repos/{repo}/issues/{num}/comments",
       {"body": f"Trust lowered for {', '.join(f'`{m}`' for m in new['modules'])}: the spot-check on #{new['pr']} "
                f"found a problem (\"{new['reason']}\", @{new['by']}). Their files will be read in full until {new['until']}."})


def inline_findings(repo: str, number: int, sha: str, report: dict, existing: list[dict]) -> None:
    """Each finding as a comment on its line in "Files changed", once per commit."""
    have = "\n".join(c.get("body") or "" for c in existing)
    comments = []
    for f in report["judge"]["accepted"]:
        mark = FINDING_MARK.format(id=f["id"], sha=sha[:12])
        if mark in have:
            continue
        ev = next((e for e in f.get("evidence", []) if e["kind"] != " "), None)
        if not ev:
            continue
        side = "LEFT" if ev["kind"] == "-" else "RIGHT"
        comments.append({"path": f["file"], "line": ev["line"], "side": side,
                         "body": f"{mark}\n**{f['id']}** · {brief.short(f['claim'], f['id'])}\n\n"
                                 f"Reply here with `/accept {f['id']}` if it is real, or `/refute {f['id']} \"why\"` if not. "
                                 f"`/explain {f['id']}` for more."})
    if comments:
        try:
            gh("POST", f"/repos/{repo}/pulls/{number}/reviews",
               {"commit_id": sha, "event": "COMMENT", "comments": comments,
                "body": f"Earned-Trust: {len(comments)} finding{'s' if len(comments) != 1 else ''} on the lines they are about."})
        except Exception as e:  # a line GitHub won't comment on must not stop the review
            print(f"inline comments skipped: {e}")


def reply_to(repo: str, number: int, comment: dict, kind: str, replies: list[str]) -> None:
    text = "\n\n".join(replies)
    if kind == "review":
        gh("POST", f"/repos/{repo}/pulls/{number}/comments/{comment['id']}/replies", {"body": text})
    else:
        quote = "\n".join("> " + l for l in (comment["body"] or "").strip().splitlines()[:6])
        gh("POST", f"/repos/{repo}/issues/{number}/comments", {"body": f"{quote}\n\n{text}"})


def main(target: str | None) -> int:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    name = os.environ["GITHUB_EVENT_NAME"]
    repo = os.environ["GITHUB_REPOSITORY"]
    trigger, trigger_kind = None, None
    if name in ("issue_comment", "pull_request_review_comment"):
        if name == "issue_comment" and "pull_request" not in event["issue"]:
            print("not a pull request comment")
            return 0
        trigger = event["comment"]
        trigger_kind = "review" if name == "pull_request_review_comment" else "issue"
        if trigger["user"]["type"] == "Bot" or not any(l.strip().startswith("/") for l in (trigger["body"] or "").splitlines()):
            print("no slash command in the comment")
            return 0
        num = event["issue"]["number"] if name == "issue_comment" else event["pull_request"]["number"]
        pr = gh("GET", f"/repos/{repo}/pulls/{num}")
        target = None  # tests ran on the pull_request event; reuse that result
    else:
        pr = event["pull_request"]
    number, sha = pr["number"], pr["head"]["sha"]

    diff = gh("GET", f"/repos/{repo}/pulls/{number}", accept="application/vnd.github.v3.diff")
    n = issue_number(pr)
    meta = {"issue": n, "sha": sha, "subject": pr["title"], "author": pr["user"]["login"]}
    change = sources.make(f"pr-{number}", meta, issue_text(n, repo), diff, f"GitHub {repo}#{number}")
    run_dir = pipeline.RUNS / f"pr-{number}"
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)

    ledger_i, trust_events = load_trust_events(repo)
    ledger.EVENTS[:] = trust_events
    comments = [dict(c, _kind="issue") for c in all_comments(repo, number)]
    rcomments = [dict(c, _kind="review") for c in review_comments(repo, number)]
    mine = next((c for c in comments if MARK in (c.get("body") or "")), None)
    llm_cache = sources.CACHE / change.branch / "llm"
    shutil.rmtree(llm_cache, ignore_errors=True)
    if trigger:
        restore_llm(mine["body"] if mine else "", sha, llm_cache)
    ev = evidence(change, run_dir, Path(target).resolve() if target else None, mine["body"] if mine else "")
    if ev:
        (run_dir / "tests.json").write_text(json.dumps(ev, indent=1))

    # on comment runs, only the saved answers count: offline=True never calls the LLM again
    report = pipeline.review(change, offline=bool(trigger) or not llm.configured(), run_dir=run_dir)

    # Replay the PR's slash commands (PR comments and line comments) written since its last commit.
    commit_at = gh("GET", f"/repos/{repo}/commits/{sha}")["commit"]["committer"]["date"]
    st = commands.load(run_dir)
    st["published_at"] = max(mine["created_at"], commit_at) if mine else commit_at
    commands.save(run_dir, st)
    log, mine_replies, names = [], [], {}
    for c in sorted(comments + rcomments, key=lambda c: c["created_at"]):
        body = c.get("body") or ""
        if c["user"]["type"] == "Bot" or MARK in body or "earned-trust-finding" in body:
            continue
        lines = [l.strip() for l in body.splitlines() if l.strip().startswith("/")]
        if not lines:
            continue
        is_trigger = trigger is not None and c["id"] == trigger["id"]
        if ts(c["created_at"]) < ts(commit_at):
            msg = "Ignored: this was written before the latest commit, and a new commit starts a new review. Please send it again."
            log.append(f"- @{c['user']['login']}: {msg}")
            if is_trigger:
                mine_replies.append(msg)
            continue
        for l in lines:
            ok = c["author_association"] in SIGNERS
            signed_as = with_name(l, c["user"]["login"], names)
            if signed_as is None:
                reply = "Your GitHub profile has no name, so write it: `/sign \"Your Full Name\"`."
            else:
                l = signed_as
                _, reply = commands.apply(report, run_dir, c["user"]["login"], l, at=c["created_at"], can_sign=ok)
            if not l.lower().startswith("/explain"):
                log.append(f"- @{c['user']['login']}: `{l[:70]}`  \n  {reply}")
            if is_trigger:
                mine_replies.append(f"`{l[:70]}`\n{reply}" if len(lines) > 1 else reply)
    state = commands.load(run_dir)
    gate = commands.gate(report, state)

    # A new escape teaches the ledger: the hidden files' folders lose trust.
    sc = state.get("spotcheck") or {}
    if trigger and sc.get("result") == "escape" and sc.get("at") == trigger["created_at"]:
        from datetime import datetime, timedelta, timezone
        mods = sorted({ledger.module_of(p) for p in report["router"]["hidden"]})
        until = (datetime.now(timezone.utc) + timedelta(days=90)).strftime("%Y-%m-%d")
        save_trust_event(repo, ledger_i, trust_events, {"kind": "escape", "pr": number, "by": sc["by"], "at": sc["at"],
                                                         "reason": sc.get("quote", ""), "modules": mods, "until": until})

    hidden = f"<!-- earned-trust-evidence {json.dumps({k: v for k, v in ev.items() if k != 'log_tail'})} -->" if ev else ""
    text = brief.render(report, state)
    if log:
        text += "\n<details><summary>Replies so far</summary>\n\n" + "\n".join(log[-30:]) + "\n\n</details>\n"
    m = json.dumps(metrics(pr, sha, report, state, gate)).replace("--", "- -")
    body = f"{MARK}\n{hidden}\n{save_llm(llm_cache, sha)}\n<!-- earned-trust-metrics {m} -->\n{text}"
    if mine:
        gh("PATCH", f"/repos/{repo}/issues/comments/{mine['id']}", {"body": body})
    else:
        gh("POST", f"/repos/{repo}/issues/{number}/comments", {"body": body})
    if name == "pull_request":
        inline_findings(repo, number, sha, report, rcomments)
    if trigger and mine_replies:
        reply_to(repo, number, trigger, trigger_kind, mine_replies)

    if gate["conclusion"] == "success":
        title = "Signed by " + " and ".join(x["name"] for x in state["signatures"])
    else:
        k = len(gate["todo"])
        title = f"Waiting for {k} {'reply' if k == 1 else 'replies'} on the PR: {gate['todo'][0]['what']}"
    out = {"title": title[:240], "summary": "\n".join(brief.summary(report)) +
           ("" if gate["conclusion"] == "success" else "\n\n**Still to do:**\n" + "\n".join(f"- {t['what']} → {t['how']}" for t in gate["todo"]))}
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
