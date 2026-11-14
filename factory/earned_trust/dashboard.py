"""The trust dashboard: one static HTML page from bench/report.json and the
receipts. Every number carries a chip naming its source; nothing is drawn
that was not measured."""

from __future__ import annotations

import html
import json

from .sources import FACTORY

ROOT = FACTORY.parent
OUT = ROOT / "dashboard" / "index.html"

CSS = """
:root{color-scheme:light;--bg:#f6f6f4;--surface:#fcfcfb;--border:#e4e3df;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;
--s1:#2a78d6;--s1b:#a9c8ef;--rest:#d9d8d3;--good:#008300;--bad:#e34948;--chip:#efeeea}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#111110;--surface:#1a1a19;--border:#2e2e2c;
--ink:#f0efec;--ink2:#c3c2b7;--muted:#8f8e88;--s1:#3987e5;--s1b:#2b4d78;--rest:#3a3a37;--good:#3fae3f;--bad:#e66767;--chip:#262624}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#111110;--surface:#1a1a19;--border:#2e2e2c;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8f8e88;
--s1:#3987e5;--s1b:#2b4d78;--rest:#3a3a37;--good:#3fae3f;--bad:#e66767;--chip:#262624}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1080px;margin:0 auto;padding:32px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{font-size:17px;margin:0 0 4px}
.sub{color:var(--ink2);margin:0 0 24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-bottom:24px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:16px}
.tile .n{font-size:30px;font-weight:650;font-variant-numeric:tabular-nums}.tile .l{color:var(--ink2);font-size:13px}
.chip{display:inline-block;background:var(--chip);color:var(--ink2);border-radius:999px;padding:1px 8px;font-size:11px;margin-top:6px}
.desc{color:var(--ink2);font-size:13px;margin:0 0 12px}table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--border);vertical-align:top}th{color:var(--ink2);font-weight:600}
td.num{text-align:right;font-variant-numeric:tabular-nums}.ok{color:var(--good)}.no{color:var(--bad)}
.bar{display:flex;height:22px;border-radius:4px;overflow:hidden;gap:2px;background:var(--surface)}.bar span{display:block;height:100%}
.row{display:grid;grid-template-columns:150px 1fr 110px;gap:10px;align-items:center;margin:8px 0}.row .lab{font-size:13px}
.row .val{font-size:13px;color:var(--ink2);text-align:right;font-variant-numeric:tabular-nums}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--ink2);margin-top:8px}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.scroll{overflow-x:auto}@media(max-width:600px){.row{grid-template-columns:90px 1fr 70px}}
"""


def chip(s: str) -> str:
    return f'<span class="chip">source: {html.escape(s)}</span>'


def tile(n: str, label: str, src: str) -> str:
    return f'<div class="card tile"><div class="n">{n}</div><div class="l">{html.escape(label)}</div>{chip(src)}</div>'


def build() -> str:
    r = json.loads((FACTORY / "bench" / "report.json").read_text())
    s, j, h, p, sw = r["seeded"], r["judge"], r["hallucinations_real"], r["precision"], r["shape_preserving_sweep"]
    P = [f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
         f"<title>Earned-Trust Dashboard</title><style>{CSS}</style></head><body><main>",
         "<h1>Earned-Trust Dashboard</h1>",
         f"<p class=sub>AI reviews. Humans sign. Evidence decides. Generated {r['generated_at']} by "
         "<code>python -m earned_trust bench</code>; every number names where it comes from.</p>",
         "<div class=grid>",
         tile(f"{s['caught']}/{s['total']}", "seeded defects that reached a human", s["source"]),
         tile(f"{s['flagged']}/{s['total']}", "…flagged by name (finding, outlier, trigger, tracer)", s["source"]),
         tile(f"{j['rejected']}/{j['corruptions']}", f"corrupted citations rejected by the judge ({j['accepted']}/{j['controls']} real ones kept)", j["source"]),
         tile(f"{h['rejected']}/{h['accusations']}", "accusations rejected in the real runs (all from our own LLM-written draft)", h["source"]),
         tile(f"{p['real']}/{p['real'] + p['false_positive']}", "verified findings labelled real (small sample, provisional labels)", p["source"]),
         "</div>"]

    # what the human reads
    P += live_section()
    P += ["<div class=card><h2>What the human reads</h2><p class=desc>Changed lines per branch: read by the signer, "
          "summarized as test evidence (named in the claims matrix), or hidden as mechanical (pattern-checked and sampled). "
          "T2 changes are read in full: the factory saves no time there, on purpose.</p>"]
    for b in r["replay"]["branches"]:
        tot = b["lines"]
        must = b["lines_must_read"]
        # the bench row has no split of the rest; read it from the run if present
        rest_tests = 0
        rp = ROOT / "runs" / b["branch"] / "router.json"
        if rp.exists():
            rest_tests = json.loads(rp.read_text())["read"]["lines_tests_summarized"]
        hidden = tot - must - rest_tests
        seg = lambda n, var, what: (f'<span style="width:{100 * n / tot:.2f}%;background:var({var})" '
                                    f'title="{what}: {n:,} lines"></span>' if n else "")
        P.append(f'<div class=row><div class=lab><b>#{b["branch"][-4:]}</b> · {b["tier"]}</div>'
                 f'<div class=bar role=img aria-label="{must} of {tot} lines read">{seg(must, "--s1", "read by the human")}'
                 f'{seg(rest_tests, "--s1b", "tests, summarized")}{seg(hidden, "--rest", "mechanical, hidden")}</div>'
                 f'<div class=val>{must:,} of {tot:,}</div></div>')
    P += ['<div class=legend><span><i style="background:var(--s1)"></i>read by the human</span>'
          '<span><i style="background:var(--s1b)"></i>tests, summarized</span><span><i style="background:var(--rest)"></i>mechanical, hidden + sampled</span></div>',
          chip(r["replay"]["source"]), "</div>"]

    # sweep
    so, cc = sw["shape_only"], sw["with_content_check"]
    P += ["<div class=card><h2>Defects that keep the shape</h2>"
          f"<p class=desc>One snapshot of #2297 at a time gets <code>SuppressMessage</code> instead of <code>ExcludeFromCodeCoverage</code>: "
          f"same shape, different words. {so['mutants']} mutants. With the shape check alone only the 5% spot-check stands between them and the merge; "
          "this measurement is why the classifier now compares the text inside each pattern too.</p>"]
    for name, v in (("shape check only", so), ("+ text inside the pattern", cc)):
        P.append(f'<div class=row><div class=lab>{name}</div><div class=bar role=img aria-label="{v["escaped"]} escaped">'
                 + (f'<span style="width:{100 * v["escaped"] / v["mutants"]:.2f}%;background:var(--bad)" title="escaped: {v["escaped"]}"></span>' if v["escaped"] else "")
                 + (f'<span style="width:{100 * v["sampled"] / v["mutants"]:.2f}%;background:var(--s1b)" title="caught by the sample: {v["sampled"]}"></span>' if v["sampled"] else "")
                 + (f'<span style="width:{100 * v["flagged"] / v["mutants"]:.2f}%;background:var(--good)" title="flagged: {v["flagged"]}"></span>' if v["flagged"] else "")
                 + f'</div><div class=val>{v["escaped"]} escaped</div></div>')
    P += ['<div class=legend><span><i style="background:var(--bad)"></i>escaped</span><span><i style="background:var(--s1b)"></i>caught only by the spot-check sample</span>'
          '<span><i style="background:var(--good)"></i>flagged as outlier</span></div>', chip(sw["source"]), "</div>"]

    # guardrail
    sess = r["sessions"]["rows"]
    live = [x for x in sess if not x["simulated"] and x["minutes_brief_to_sign"] is not None]
    P += ["<div class=card><h2>Guardrail: review time may go down only while escapes stay flat</h2>"
          "<p class=desc>Minutes are measured from brief to <code>/sign</code> in live sessions only; scripted demo sessions have no timing. "
          "If a seeded defect escapes, the module it hid in loses a level of trust automatically.</p>",
          "<table><tr><th>Signal</th><th>Now</th><th>Source</th></tr>",
          f"<tr><td>Human review minutes (median, live sessions)</td><td>{_median([x['minutes_brief_to_sign'] for x in live]) if live else 'no live session recorded yet'}</td><td>{html.escape(r['sessions']['source'])}</td></tr>",
          f"<tr><td>Seeded defects escaped</td><td>{s['total'] - s['caught']} of {s['total']}</td><td>seeded</td></tr>",
          f"<tr><td>Shape-preserving escapes</td><td>{cc['escaped']} of {cc['mutants']}</td><td>seeded</td></tr>",
          f"<tr><td>Trust demotions triggered</td><td>{len(r['guardrail']['actions']) or 'none'}</td><td>{html.escape(r['guardrail']['source'])}</td></tr>",
          f"<tr><td>Modules EARNED / PROBATION / REVOKED</td><td>{r['trust']['counts']['EARNED']} / {r['trust']['counts']['PROBATION']} / {r['trust']['counts']['REVOKED']}</td><td>{html.escape(r['trust']['source'])}</td></tr>",
          "</table></div>"]

    # sessions
    P += ["<div class=card><h2>Signing sessions</h2><div class=scroll><table><tr><th>Branch</th><th>Kind</th><th>Accepted</th><th>Refuted</th><th>Spot-check</th><th>Signed</th><th>Minutes</th></tr>"]
    for x in sess:
        P.append(f"<tr><td>{x['branch']}</td><td>{'simulated (scripted)' if x['simulated'] else 'live'}</td><td class=num>{x['accepted']}</td>"
                 f"<td class=num>{x['refuted']}</td><td>{x['spotcheck'] or '—'}</td><td>{'yes' if x['signed'] else 'no'}</td>"
                 f"<td class=num>{x['minutes_brief_to_sign'] if x['minutes_brief_to_sign'] is not None else '—'}</td></tr>")
    acc = sum(x["accepted"] for x in sess)
    ref = sum(x["refuted"] for x in sess)
    P += [f"</table></div><p class=desc style='margin-top:8px'>Finding acceptance: {acc} accepted, {ref} refuted"
          f"{' (all from scripted sessions: not evidence of usefulness yet)' if all(x['simulated'] for x in sess) else ''}.</p>{chip(r['sessions']['source'])}</div>"]

    # seeded table
    P += ["<div class=card><h2>Seeded defects</h2><div class=scroll><table><tr><th>Id</th><th>Branch</th><th>Defect</th><th>Result</th><th>Caught by</th><th>Tier</th></tr>"]
    for m in s["mutants"]:
        cls = "ok" if m["result"] != "ESCAPED" else "no"
        P.append(f"<tr><td>{m['id']}</td><td>#{m['branch'][-4:]}</td><td>{html.escape(m['what'])}</td><td class={cls}>{m['result']}</td>"
                 f"<td>{html.escape(', '.join(m['caught_by']) or ('in the must-read set' if m['result'] == 'ROUTED' else 'spot-check sample' if m['result'] == 'SAMPLED' else '—'))}</td>"
                 f"<td>{m['base_tier']}→{m['tier']}</td></tr>")
    P += [f"</table></div>{chip(s['source'])}</div>"]

    # precision table
    P += ["<div class=card><h2>Findings on the real branches</h2><div class=scroll><table><tr><th>Branch</th><th>Finding</th><th>Label</th><th>Note</th></tr>"]
    for x in p["rows"]:
        P.append(f"<tr><td>#{x['branch'][-4:]}</td><td>{x['finding']}</td><td>{x['label']}</td><td>{html.escape(x['note'])}</td></tr>")
    P += [f"</table></div>{chip(p['source'])}</div>",
          "<p class=desc>Earned-Trust PR Factory · runs on every pull request with GitHub Actions</p>",
          "</main></body></html>"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(P))
    return str(OUT.relative_to(ROOT))


def live_section() -> list[str]:
    """This repository's pull requests, as the GitHub API reports them."""
    p = FACTORY / "bench" / "live.json"
    if not p.exists():
        return ["<div class=card><h2>Live: this repository's pull requests</h2><p class=desc>Not collected in this build "
                "(run <code>python3 factory/et.py live</code> with a GITHUB_TOKEN).</p></div>"]
    d = json.loads(p.read_text())
    s = d["summary"]
    src = f"{d['source']}, collected {d['collected_at']}"
    fmt_min = lambda m: "—" if m is None else (f"{m:.0f} min" if m < 120 else f"{m / 60:.1f} h")
    rate = lambda a: "no answers yet" if a["acceptance_rate"] is None else f"{a['accepted']} of {a['accepted'] + a['refuted']} accepted"
    P = ["<div class=card><h2>Live: this repository's pull requests</h2>",
         "<p class=desc>Read from GitHub on every build and after every review: the four AI-written PRs of the challenge, "
         "reviewed by the Action. Times run from the brief to the signature, and from opening to merge. "
         "Findings are split by who raised them: deterministic rules or the AI model.</p>",
         "<div class=grid>",
         tile(f"{s['lines_to_humans']:,} of {s['lines_total']:,}", f"changed lines sent to a person ({s['share_lines_to_humans']:.0%})", "GitHub API"),
         tile(f"{s['signed']} of {s['reviewed']}", "PRs signed", "GitHub API"),
         tile(fmt_min(s["median_minutes_to_sign"]), "median time from brief to signature" + ("" if s["signed"] else " (no PR signed yet)"), "GitHub API"),
         tile(rate(s["answers"]["rules"]), f"rule findings ({s['answers']['rules']['open']} still open)", "GitHub API"),
         tile(rate(s["answers"]["ai"]), f"AI findings ({s['answers']['ai']['open']} still open)", "GitHub API"),
         "</div>",
         "<div class=scroll><table><tr><th>PR</th><th>Tier</th><th>Lines to a person</th><th>Findings (rules / AI)</th>"
         "<th>Accepted / refuted</th><th>Gate</th><th>Brief → signature</th><th>Open → merge</th></tr>"]
    for r in d["prs"]:
        n_rules = sum(1 for f in r["findings"] if f["source"] == "rules")
        n_ai = len(r["findings"]) - n_rules
        acc = sum(1 for a in r["answers"] if a["verdict"] == "accepted")
        ref = sum(1 for a in r["answers"] if a["verdict"] == "refuted")
        gate = "<span class=ok>signed</span>" if r["gate"] == "success" else "waiting"
        share = f"{r['lines_must_read']:,} of {r['lines_total']:,}" if r["lines_total"] else "—"
        P.append(f"<tr><td><a href='{html.escape(r['url'])}'>#{r['pr']}</a> {html.escape(r['title'][:60])}</td><td>{r['tier']}</td>"
                 f"<td class=num>{share}</td><td class=num>{n_rules} / {n_ai}</td><td class=num>{acc} / {ref}</td><td>{gate}</td>"
                 f"<td class=num>{fmt_min(r['minutes_to_sign'])}</td><td class=num>{fmt_min(r['minutes_to_merge'])}</td></tr>")
    P += ["</table></div>",
          f"<p class=desc style='margin-top:8px'>Spot-check escapes recorded in the trust ledger: {s['escapes']}. "
          "A rising number of escapes, or of reverts after signed merges, would mean shorter reviews are costing quality.</p>",
          chip(src), "</div>"]
    return P


def _median(xs: list[float]) -> float:
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else round((xs[n // 2 - 1] + xs[n // 2]) / 2, 1)
