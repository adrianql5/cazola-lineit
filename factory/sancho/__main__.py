"""Sancho: AI reviews. Humans sign. Evidence decides.

    python -m sancho review --branch ju26-issue-2297 [--offline] [--no-llm]
    python -m sancho cmd --branch B --as LOGIN '/decide ABS-1 keep-guard "reason"'
    python -m sancho status --branch B
    python -m sancho test --branch B          (dotnet test of the tests the change adds)
    python -m sancho github --target DIR      (inside GitHub Actions, on every PR)
    python -m sancho live [--repo owner/name] (measurements from the repo's PRs; needs GITHUB_TOKEN)
    python -m sancho protect --repo owner/name [--branch B]  (the merge gate as a ruleset; admin token)
    python -m sancho demo                     (offline: 4 briefs, sessions, bench, dashboard)
    python -m sancho bench | dashboard | ledger | models
"""

from __future__ import annotations

import argparse
import sys

from . import commands, ledger, llm, pipeline, sources


def status_line(rep: dict, state: dict) -> str:
    n = len(commands.todo(rep, state))
    if not n:
        return "Status: signed ✅ (receipt: runs/" + rep["change"]["branch"] + "/receipt.md)"
    return f"Status: waiting for {n} more {'reply' if n == 1 else 'replies'} before it can merge."


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sancho", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("review", help="review the cached branches (or one of them)")
    r.add_argument("--branch", action="append")
    r.add_argument("--offline", action="store_true", help="replay cache only: no git, no network")
    r.add_argument("--no-llm", action="store_true")
    c = sub.add_parser("cmd", help="run a slash command on a review, as LOGIN")
    c.add_argument("--branch", required=True)
    c.add_argument("--as", dest="actor", required=True)
    c.add_argument("--simulated", action="store_true")
    c.add_argument("text")
    s = sub.add_parser("status")
    s.add_argument("--branch", required=True)
    te = sub.add_parser("test", help="run the tests a change adds (dotnet, or the .NET SDK image via Docker)")
    te.add_argument("--branch", required=True)
    te.add_argument("--repo")
    te.add_argument("--image", default="mcr.microsoft.com/dotnet/sdk:8.0")
    te.add_argument("--ignore-global-json", action="store_true",
                    help="build with --image although global.json pins another SDK (recorded as a deviation)")
    g = sub.add_parser("github", help="GitHub Actions: review the PR of this event, replay its commands, set the check")
    g.add_argument("--target", help="checkout of the PR head, to run its tests (pull_request events)")
    g.add_argument("--reset", type=int, metavar="PR", help="start PR's review again: earlier commands stop counting, same findings")
    pt = sub.add_parser("protect", help="set up the merge gate (a branch ruleset) on a repository; needs admin rights")
    pt.add_argument("--repo", required=True)
    pt.add_argument("--branch", action="append", default=[], help="another branch to protect (the default branch always is)")
    pt.add_argument("--dry-run", action="store_true", help="print the ruleset, change nothing")
    lv = sub.add_parser("live", help="measurements from this repository's pull requests (needs GITHUB_TOKEN)")
    lv.add_argument("--repo")
    sub.add_parser("demo")
    sub.add_parser("bench")
    sub.add_parser("dashboard")
    sub.add_parser("ledger")
    sub.add_parser("models")
    a = ap.parse_args(argv)

    if a.cmd == "review":
        for br in a.branch or sources.branches():
            rep = pipeline.review(sources.load(br, offline=a.offline), offline=a.offline, use_llm=not a.no_llm)
            rd = rep["router"]["read"]
            print(f"{br}: {rep['router']['tier']} · read {rd['lines_must_read']}/{rd['lines_total']} lines · "
                  f"{len(rep['judge']['accepted'])} findings, {len(rep['judge']['rejected'])} rejected · "
                  f"{len(rep['abstentions'])} abstained · runs/{br}/brief.md")
        return 0
    if a.cmd == "cmd":
        rep = pipeline.load_report(a.branch)
        state, reply = commands.apply(rep, pipeline.RUNS / a.branch, a.actor, a.text, simulated=a.simulated)
        sc = state.get("spotcheck") or {}
        if a.text.strip().startswith("/spotcheck escape") and sc.get("result") == "escape" and not a.simulated:
            from datetime import datetime, timedelta
            ledger.record_local({"kind": "escape", "pr": a.branch, "by": a.actor, "at": sc["at"], "reason": sc.get("quote", ""),
                                 "modules": sorted({ledger.module_of(p) for p in rep["router"]["hidden"]}),
                                 "until": (datetime.utcnow() + timedelta(days=90)).strftime("%Y-%m-%d")})
            reply += f"\nRecorded in {ledger.LOCAL_EVENTS.relative_to(ledger.ROOT)}: the next reviews read these folders in full."
        print(reply)
        print(status_line(rep, state))
        return 0
    if a.cmd == "status":
        rep = pipeline.load_report(a.branch)
        state = commands.load(pipeline.RUNS / a.branch)
        print(status_line(rep, state))
        for t in commands.todo(rep, state):
            print(f"- {t['what']} → {t['how']}")
        return 0
    if a.cmd == "test":
        from . import worker
        res = worker.run(a.branch, a.repo, a.image, a.ignore_global_json)
        print(f"{a.branch}: tests {res['status']} — {res.get('why', '')}")
        return 0 if res["status"] in ("PASS", "NOT RUN") else 1
    if a.cmd == "github":
        from . import github
        return github.main(a.target, a.reset)
    if a.cmd == "protect":
        from . import protect
        protect.main(a.repo, a.branch, a.dry_run)
        return 0
    if a.cmd == "live":
        from . import live
        live.main(a.repo)
        return 0
    if a.cmd == "ledger":
        t = ledger.trust_table()
        for m, v in sorted(t["modules"].items()):
            print(f"{v['state']:<10} {m}  ({v['commits']} commits, {v['reverts']} reverts, {v['fix_followups']} fix follow-ups)")
        return 0
    if a.cmd == "models":
        try:
            print("\n".join(llm.models()))
        except llm.LLMUnavailable as e:
            print(f"LLM unavailable: {e}", file=sys.stderr)
            return 1
        return 0
    if a.cmd == "demo":
        from . import demo
        demo.run()
        return 0
    if a.cmd == "bench":
        from bench import run as bench_run
        bench_run.main()
        return 0
    if a.cmd == "dashboard":
        from . import dashboard
        print(dashboard.build())
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
