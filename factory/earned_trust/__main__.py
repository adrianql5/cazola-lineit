"""Earned-Trust PR Factory: AI reviews. Humans sign. Evidence decides.

    python -m earned_trust review --branch ju26-issue-2297 [--offline] [--no-llm]
    python -m earned_trust cmd --branch B --as LOGIN '/decide ABS-1 keep-guard "reason"'
    python -m earned_trust status --branch B
    python -m earned_trust test --branch B          (dotnet test of the tests the change adds)
    python -m earned_trust github --target DIR      (inside GitHub Actions, on every PR)
    python -m earned_trust demo                     (offline: 4 briefs, sessions, bench, dashboard)
    python -m earned_trust bench | dashboard | ledger | models
"""

from __future__ import annotations

import argparse
import json
import sys

from . import commands, ledger, llm, pipeline, sources


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="earned_trust", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
        print(reply)
        print("gate:", commands.gate(rep, state)["conclusion"])
        return 0
    if a.cmd == "status":
        rep = pipeline.load_report(a.branch)
        print(json.dumps(commands.gate(rep, commands.load(pipeline.RUNS / a.branch)), indent=1))
        return 0
    if a.cmd == "test":
        from . import worker
        res = worker.run(a.branch, a.repo, a.image, a.ignore_global_json)
        print(f"{a.branch}: tests {res['status']} — {res.get('why', '')}")
        return 0 if res["status"] in ("PASS", "NOT RUN") else 1
    if a.cmd == "github":
        from . import github
        return github.main(a.target)
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
