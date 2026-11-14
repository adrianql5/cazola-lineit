"""The Evidence Brief: a GitHub comment, story first.

Five lines on top that a human can read on a Friday afternoon, then the
evidence in <details> blocks. Every sentence in it comes from a stage's JSON;
the brief is written by a template, not by a model.
"""

from __future__ import annotations

from pathlib import PurePosixPath

ICON = {"VERIFIED": "✅", "PARTIAL": "🟡", "UNVERIFIED": "⚪", "CONTRADICTED": "❌"}


def short(path: str, n: int = 60) -> str:
    return path if len(path) <= n else "…" + path[-(n - 1):]


def story(r: dict) -> list[str]:
    ch, cl, rt, au, ab = r["change"], r["classifier"], r["router"], r["auditor"], r["abstentions"]
    c = cl["counts"]
    parts = []
    for k in ("semantic", "public-contract", "test", "docs", "mechanical"):
        if c.get(k):
            parts.append(f"{c[k]} {k}")
    what = f"**What:** {ch['subject']} — {ch['files']} files ({', '.join(parts)})."
    why = f"**Why:** issue [#{ch['issue']}]({ch['issue_url']}): \"{ch['issue_title'].rstrip('.')}\"."
    oos = au["out_of_scope"]
    if oos:
        o = oos[0]
        extra = f" It is what changes {len(au['outlier_links'])} of {cl['snapshots']} snapshots." if au["outlier_links"] else ""
        also = (f"**Also touches:** `{PurePosixPath(o['file']).name}:{o['line']}`, "
                f"{'a whitespace-only change' if o['formatting_only'] else 'a change'} no requirement asks for.{extra}")
    elif cl["triggers"]:
        rules = sorted({t["rule"] for t in cl["triggers"]})
        also = f"**Also touches:** {', '.join(f'`{x}`' for x in rules)}."
    else:
        also = "**Also touches:** nothing outside the issue that the auditor could find."
    rd = rt["read"]
    risk = (f"**Risk:** {rt['tier']} — {rt['reasons'][0]}. You read **{rd['lines_must_read']:,} of "
            f"{rd['lines_total']:,}** changed lines; {rd['files_hidden']} mechanical files summarized, "
            f"{r['sampler'].get('n', 0)} sampled.")
    if ab:
        a = ab[0]
        watch = f"**Decide:** {a['decision']} → `ABSTAINED`, the AI will not decide this ({len(ab)} in total)."
    else:
        watch = "**Decide:** nothing: the AI found no decision outside its remit."
    return [what, why, also, risk, watch]


def gate_lines(r: dict, state: dict | None = None) -> list[str]:
    state = state or {}
    done = lambda ok: "x" if ok else " "
    out = []
    if r["sampler"]["population"]:
        out.append(f"- [{done(state.get('spotcheck'))}] `/spotcheck clean|escape` after looking at the {r['sampler']['n']} sampled files")
    for a in r["abstentions"]:
        d = state.get("decisions", {}).get(a["id"])
        out.append(f"- [{done(d)}] `/decide {a['id']} <{'|'.join(a['options'])}> \"<reason>\"` — {a['kind']}")
    for f in r["judge"]["accepted"]:
        v = state.get("findings", {}).get(f["id"])
        out.append(f"- [{done(v)}] `/accept {f['id']}` or `/refute {f['id']} \"<evidence>\"`")
    who = "two owners (second reviewer required)" if r["router"]["second_reviewer"] else "the owner"
    out.append(f"- [{done(state.get('signed_complete'))}] `/sign \"<Full Name>\"` by {who}")
    return out


def render(r: dict, state: dict | None = None) -> str:
    ch, rt = r["change"], r["router"]
    L = [f"## Earned-Trust Evidence Brief · #{ch['issue']} · `{ch['branch']}` @ `{ch['sha'][:10]}`", ""]
    if rt["tier"] == "T2" or r["abstentions"]:
        head = f"**{rt['tier']}**"
        if rt["tier"] == "T2":
            head += " · full human read required"
        if r["abstentions"]:
            n = len(r["abstentions"])
            head += f" · {n} decision{'s' if n != 1 else ''} the AI refused to make"
        L += ["> [!CAUTION]", f"> {head}", ""]
    L += [f"{i}. {s}" for i, s in enumerate(story(r), 1)]
    L += ["", "**To turn `earned-trust/human-accountability-gate` green:**", *gate_lines(r, state), ""]

    # Claims <-> Evidence
    tr = r["tracer"]
    counts = " · ".join(f"{ICON[k]} {k} {v}" for k, v in sorted(tr["counts"].items()))
    L += [f"<details><summary><b>Claims ↔ Evidence</b> — {counts}</summary>", "",
          f"Requirements: `{tr['requirements_source']}` ({tr['curated_by']}). Tests: **{tr['execution']['status']}** — {tr['execution'].get('why', '')}", "",
          "| Claim | Status | Implementation | Tests in this change | Why |", "|---|---|---|---|---|"]
    for c in tr["claims"]:
        impl = ", ".join(f"`{short(i['file'], 34)}:{i['line']}`" for i in c["implementation"][:2]) or "—"
        tests = ", ".join(f"`{t['test']}`" for t in c["tests"][:2]) + (f" +{len(c['tests']) - 2}" if len(c["tests"]) > 2 else "") or "—"
        claim = c["claim"].replace("|", "\\|")
        L.append(f"| **{c['id']}** {claim[:140]} | {ICON[c['status']]} {c['status']} | {impl} | {tests} | {c['why'][:120]} |")
    L += ["", "</details>", ""]

    # Findings
    acc = r["judge"]["accepted"]
    L += [f"<details open><summary><b>Findings</b> — {len(acc)} with a citation the judge verified</summary>", ""]
    if not acc:
        L.append("None.")
    for f in acc:
        L += [f"**{f['id']}** · {f['severity']} · {f['source']} · `{f['file']}:{f['line_start']}`" +
              (f" (also lines {', '.join(map(str, f.get('also_at', [])))})" if f.get("also_at") else ""), "",
              f"{f['claim']}", ""]
        snippet = "\n".join(f"{e['line']:>5} {e['kind']}{e['text']}" for e in f.get("evidence", [])[:3])
        if snippet:
            L += ["```diff", snippet, "```", ""]
        if f.get("also_raised_by"):
            L += [f"Also raised by: {', '.join(f['also_raised_by'])}.", ""]
    L += ["*The judge verifies the citation, not the argument: the reasoning is the AI's until you `/accept` it.*", "", "</details>", ""]

    # Abstentions
    ab = r["abstentions"]
    L += [f"<details{' open' if ab else ''}><summary><b>What the AI refused to decide</b> — {len(ab)}</summary>", ""]
    if not ab:
        L.append("Nothing in this change matched an abstention rule.")
    for a in ab:
        L += [f"**{a['id']} · {a['kind']}** — {a['decision']}", "",
              f"- Why not the AI: {a['why_not_ai']}",
              f"- Evidence missing: {'; '.join(a['missing_evidence'])}",
              f"- Who decides: {a['who_decides']}",
              f"- Where: `{a['cite']}`",
              f"- Options: {' / '.join(f'`{o}`' for o in a['options'])}", ""]
    L += ["</details>", ""]

    # Pattern
    cl = r["classifier"]
    if cl["groups"]:
        L += [f"<details><summary><b>Pattern</b> — {cl['snapshots']} snapshots, {len(cl['outliers'])} that do not fit</summary>", ""]
        for g in cl["groups"]:
            L.append(f"- **{g['id']}** ({g['role']}, {g['size']} file{'s' if g['size'] != 1 else ''}): `{' · '.join(g['shape'])}`")
        for o in cl["outliers"]:
            res = o["residue"]
            L.append(f"  - outlier `{short(o['path'], 90)}`: beyond the pattern it adds {len(res['added'])} and removes "
                     f"{len(res['deleted'])} line(s); whitespace only: **{res['whitespace_only']}**")
        for k in r["auditor"]["outlier_links"]:
            L.append(f"  - explained by `{k['explained_by']}`: {k['why']}")
        L += ["", "</details>", ""]

    # Hallucinations
    rej = r["judge"]["rejected"]
    L += [f"<details><summary><b>Accusations the judge rejected</b> — {len(rej)}</summary>", "",
          "| Id | Source | Accusation | Why rejected |", "|---|---|---|---|"]
    for v in rej:
        L.append(f"| {v['id']} | {v['source']} | {v['claim'][:110]} | {v['why']} |")
    L += ["", "</details>", ""]

    # Not checked
    L += ["<details><summary><b>What was NOT checked</b></summary>", ""]
    L += [f"- {x['item']} — {x['why']}" for x in r["not_checked"]]
    L += ["", "</details>", ""]

    # Spot-check
    s = r["sampler"]
    L += [f"<details><summary><b>Spot-check sample</b> — {s.get('n', 0)} of {s['population']} hidden files</summary>", ""]
    if s["population"]:
        L += [f"Seed `{s['seed']}` (commit SHA): `{s['method']}`. Anyone can re-draw it.", ""]
        L += [f"- `{p}`" for p in s["sample"]]
    L += ["", "</details>", ""]

    # Phantom tests
    ph = [f for f in acc if f.get("phantom_test")]
    if ph:
        L += [f"<details><summary><b>Phantom tests</b> — {len(ph)} proposed, not run</summary>", ""]
        for f in ph:
            L += [f"For **{f['id']}**:", "```csharp", f["phantom_test"], "```", ""]
        L += ["</details>", ""]

    p = r["provenance"]
    L += ["<details><summary>Provenance</summary>", "",
          f"- Source of the diff: {ch['source']} · diff sha256 `{ch['diff_sha'][:16]}`",
          f"- Classifier: {cl['engine']}",
          f"- Prosecutor LLM: {p['llm']}",
          f"- Routing policy: {rt['policy']}" + (f" · rules sha256 `{p['policy_sha'][:16]}`" if p.get("policy_sha") else ""),
          f"- Trust ledger: {p['trust']}",
          "", "</details>", "",
          "<sub>Earned-Trust PR Factory · AI reviews. Humans sign. Evidence decides.</sub>"]
    return "\n".join(L) + "\n"
