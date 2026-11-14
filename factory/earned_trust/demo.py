"""Offline demo: briefs, receipts, benchmark and dashboard from the replay
cache, with no network and no GitHub.

The sessions below are SCRIPTED (simulated=True in every event): they show
what a signer does and produce example receipts. Their decisions are ours,
written for the demo, and they carry no timing, so the dashboard does not
count them as review minutes.
"""

from __future__ import annotations

from . import commands, pipeline, sources
from .sources import FACTORY

ROOT = FACTORY.parent

SESSIONS = {
    "ju26-issue-2297": [
        "/spotcheck clean",
        '/decide ABS-1 remove-guard "Microsoft docs list ExcludeFromCodeCoverageAttribute for netstandard2.0 and .NET Framework 4.0+; the guard only drops the feature for those users"',
        "/accept SCOPE-1",
        "/accept DRIFT-1",
        "/accept DRIFT-2",
        "/accept DRIFT-3",
        '/sign "Demo Owner"',
    ],
    "ju26-issue-2283": [
        '/decide ABS-1 narrow-to-metadata-types "Drop only diagnostics whose symbol comes from metadata; keep Location.None ones from this compilation"',
        "/accept P-GLOBAL-WRAP",
        '/sign "Demo Owner"',
    ],
    "ju26-issue-2234": [
        "/accept P-FIRST-WINS",
        '/refute P-SILENT-SKIP "Before the change the same input crashed the analyzer (AD0001); skipping after reporting MsgPack005 is the intended behaviour"',
        '/sign "Demo Owner"',
    ],
    "ju26-issue-2129": [
        "/spotcheck clean",
        '/decide ABS-1 request-changes "New public API needs a PublicAPI entry and maintainer review"',
        '/decide ABS-2 require-explicit-surrogate "A contractless default fixes a wire contract nobody chose"',
        '/decide ABS-3 keep-error "Misdeclared formatters cannot work; failing the build is right"',
        '/decide ABS-4 ask-issue-author "The issue left the design open"',
        "/accept P-TEST-EXCLUDED",
        "/accept P-DOUBLE-RUN",
        '/verify "Types from a referenced assembly get a formatter written in the consuming project, contractless unless a surrogate gives keys"',
        '/sign "Demo Owner"',
    ],
}


def run() -> None:
    print("1. Reviews (offline, replay cache)")
    for br in sources.branches():
        r = pipeline.review(sources.load(br), offline=True)
        rd = r["router"]["read"]
        print(f"   {br}: {r['router']['tier']}, read {rd['lines_must_read']}/{rd['lines_total']} lines")

    print("2. Scripted signing sessions (simulated, labelled as such)")
    for br, cmds in SESSIONS.items():
        rep = pipeline.load_report(br)
        run_dir = pipeline.RUNS / br
        proof = next(iter(rep["sampler"].get("proof_lines", {}).values()), [""])
        cmds = [f'/spotcheck clean "{proof[0]}"' if c == "/spotcheck clean" else c for c in cmds]
        for c in cmds:
            state, reply = commands.apply(rep, run_dir, "demo-owner", c, simulated=True)
        print(f"   {br}: {reply}")

    print("3. Benchmark")
    from bench import run as bench_run
    bench_run.main()

    print("4. Dashboard")
    from . import dashboard
    print("   " + dashboard.build())
