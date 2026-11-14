"""The Evidence Brief: a GitHub comment a person can read in one minute.

A few short lines on top (what, what to read, what to watch, what to decide,
the tests), then a checklist of replies, then the findings. Everything else
is folded. Every sentence comes from a stage's JSON; a template writes it,
not a model.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from . import commands, worker

STATUS = {
    "VERIFIED": "✅ tested",
    "PARTIAL": "🟡 test not run",
    "UNVERIFIED": "⚪ no test",
    "CONTRADICTED": "❌ contradicted",
}

WHY_FULL_READ = {
    "T2-PUBLIC-API": "it adds public API",
    "T2-ANALYZER-SEVERITY": "it adds rules that can break users' builds",
    "T2-TEST-EXCLUSION": "it turns tests off",
    "T2-UNSAFE": "it adds unsafe code",
    "T2-SERIALIZATION-CONTRACT": "it changes the default wire format",
}


def name(path: str) -> str:
    return PurePosixPath(path).name


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def short(claim: str, fid: str, limit: int = 280) -> str:
    """A finding in at most a couple of sentences; the rest is one /explain away."""
    if len(claim) <= limit:
        return claim
    cut = claim[:limit]
    end = max(cut.rfind(". "), cut.rfind("; "))
    cut = cut[:end + 1] if end > 80 else cut.rsplit(" ", 1)[0] + "…"
    return f"{cut} *(`/explain {fid}` for the rest)*"


def tests_line(ex: dict) -> str:
    if ex["status"] == "PASS":
        line = f"✅ {ex['passed']} of {ex['passed']} passed"
        if ex.get("deviations"):
            line += " (on a newer .NET SDK than the repo pins: the generator needs it)"
        return line
    if ex["status"] == "NOT NEEDED":
        return f"none to run: {ex['why']}"
    problem, fix = worker.explain(ex)
    icon = "❌" if ex["status"] == "FAIL" else "⚠️"
    return f"{icon} {problem} **Fix:** {fix}"


def summary(r: dict) -> list[str]:
    """The lines on top. Also used as the check run's summary."""
    ch, cl, rt, au, ab = r["change"], r["classifier"], r["router"], r["auditor"], r["abstentions"]
    rd = rt["read"]
    issue = f" (#{ch['issue']})" if ch["issue"] else ""
    out = [f"**What:** {ch['issue_title'].rstrip('.') or ch['subject']}{issue} · {plural(ch['files'], 'file')}"]
    sens = r.get("sensitivity") or {"zones": []}
    if sens["zones"]:
        z = sens["zones"][0]
        more = f" (+{len(sens['zones']) - 1} more below)" if len(sens["zones"]) > 1 else ""
        who = (" Only " + " or ".join(f"@{o}" for o in z["owners"]) + " can sign.") if z["owners"] else ""
        removed = ", a removed line" if z.get("removed") else ""
        out.append(f"**Critical:** {z['name']} at `{name(z['file'])}:{z['line']}`{removed}{more}. Full read.{who}")
    if rt["tier"] == "T2":
        rules = sorted({t["rule"] for t in cl["triggers"]})
        why = ", ".join(([f"it touches {sens['zones'][0]['name']}"] if sens["zones"] else [])
                        + [WHY_FULL_READ.get(x, x) for x in rules[:2]])
        out.append(f"**Read:** everything ({rd['lines_must_read']:,} lines), because {why}.")
    else:
        n_out = len(cl["outliers"])
        n_files = rd["files_must_read"] - n_out
        parts = [plural(n_files, "file")] + ([f"{plural(n_out, 'snapshot')} that don't match the others"] if n_out else [])
        hidden = f" The other {rd['files_hidden']} are generated and identical." if rd["files_hidden"] else ""
        out.append(f"**Read:** {' + '.join(parts)}.{hidden}")
    if au["out_of_scope"]:
        o = au["out_of_scope"][0]
        what = "a spacing change" if o["formatting_only"] else "a change"
        out.append(f"**Heads-up:** `{name(o['file'])}:{o['line']}` has {what} the issue didn't ask for.")
    elif r["judge"]["accepted"]:
        f = r["judge"]["accepted"][0]
        out.append(f"**Heads-up:** {short(f['claim'], f['id'], 160)}")
    if ab:
        more = f" (+{len(ab) - 1} more below)" if len(ab) > 1 else ""
        out.append(f"**Your call:** {ab[0]['decision']}{more} *The AI won't decide this.*")
    tr = r["tracer"]
    if tr.get("requirements_status") == "missing":
        out.append("**Requirements:** none written for this issue, so only the change's own claims were checked.")
    elif tr.get("requirements_status") == "proposed":
        out.append(f"**Requirements:** proposed by the AI from the issue; please confirm them ({tr['requirements_note']}).")
    out.append(f"**Tests:** {tests_line(tr['execution'])}")
    return out


def render(r: dict, state: dict | None = None) -> str:
    state = state or commands.load_empty()
    rt, cl = r["router"], r["classifier"]
    rd = rt["read"]
    head = (f"### 🔎 Earned-Trust review · read **{rd['lines_must_read']:,}** of {rd['lines_total']:,} lines"
            if rt["tier"] != "T2" else f"### 🔎 Earned-Trust review · full read needed ({rd['lines_total']:,} lines)")
    L = [head, ""]
    L += [f"{line}  " for line in summary(r)]
    L.append("")

    # what to reply
    todo = commands.todo(r, state)
    if todo:
        L += ["**To merge, reply to this PR with:**"]
        L += [f"- [ ] **{t['what']}** → {t['how']}" for t in todo]
    else:
        names = " and ".join(s["name"] for s in state.get("signatures", []))
        L += [f"**✅ Signed by {names}.** The receipt is in the `earned-trust/human-accountability-gate` check."]
    L.append("")

    # findings, short
    acc = r["judge"]["accepted"]
    if acc:
        L += [f"#### Findings ({len(acc)})", ""]
        for f in acc:
            v = state.get("findings", {}).get(f["id"])
            mark = f" · {v['verdict']} by @{v['by']}" if v else ""
            L += [f"**{f['id']}** · `{name(f['file'])}:{f['line_start']}`{mark}  ", short(f["claim"], f["id"])]
            ev = [e for e in f.get("evidence", []) if e["kind"] != " "][:2]
            if ev:
                L += ["```diff"] + [f"{e['kind']}{e['text'].strip()}" for e in ev] + ["```"]
            L.append("")

    # folded details
    sens = r.get("sensitivity") or {"zones": [], "escalations": []}
    if sens["zones"]:
        L += [f"<details open><summary>Why this change is treated as critical ({len(sens['zones'])})</summary>", ""]
        for z in sens["zones"]:
            who = " or ".join(f"@{o}" for o in z["owners"]) or "anyone with write access (no owner declared)"
            if z.get("teams"):
                who += f" (teams in CODEOWNERS are not checked: {', '.join(z['teams'])})"
            L += [f"**{z['name']}** · `{name(z['file'])}:{z['line']}` · {z['source']}  ",
                  f"Why: {z['why']}. Signs: {who}."]
            if z.get("text"):
                L += ["```diff", ("-" if z.get("removed") else "+") + z["text"], "```"]
            for e in z.get("evidence", [])[:3]:
                L.append(f"- also `{name(e['file'])}:{e['line']}`: {e['detector']}{' (removed line)' if e.get('removed') else ''}")
            L.append("")
        for e in sens["escalations"]:
            L.append(f"- **{e['rule']}** → {e['effect']}: {e['why']}")
        L += ["", "</details>", ""]

    ab = r["abstentions"]
    if ab:
        L += [f"<details><summary>Decisions left to you ({len(ab)})</summary>", ""]
        for a in ab:
            d = state.get("decisions", {}).get(a["id"])
            done = f" ✅ `{d['option']}` by @{d['by']}" if d else ""
            L += [f"**{a['id']}** · {a['decision']}{done}  ",
                  f"Why not the AI: {a['why_not_ai']} Who usually decides: {a['who_decides']}. Where: `{a['cite']}`.", ""]
        L += ["</details>", ""]

    claims = r["tracer"]["claims"]
    L += [f"<details><summary>What the change claims, and the proof ({len(claims)})</summary>", "",
          "| | Claim | Proof |", "|---|---|---|"]
    for c in claims:
        tests = ", ".join(f"`{t['test']}`" for t in c["tests"][:2]) or "—"
        text = c["claim"].replace("|", "\\|")
        text = text if len(text) <= 110 else text[:107] + "…"
        proof = tests if c["status"] in ("VERIFIED", "PARTIAL") else c["why"].replace("|", "\\|")[:120]
        L.append(f"| {STATUS[c['status']]} | {text} | {proof} |")
    L += ["", "</details>", ""]

    if cl["outliers"]:
        g = next((g for g in cl["groups"] if g["role"] == "dominant"), None)
        L += [f"<details><summary>Snapshots that don't match ({len(cl['outliers'])} of {cl['snapshots']})</summary>", ""]
        if g:
            L.append(f"{g['size']} snapshots all got the same lines. These did not:")
        for o in cl["outliers"]:
            extra = "only spacing differs" if o["residue"]["whitespace_only"] else "has different code"
            L.append(f"- `{name(o['path'])}`: {extra}")
        for k in r["auditor"]["outlier_links"][:1]:
            L.append(f"\nBoth come from `{k['explained_by']}`.")
        L += ["", "</details>", ""]

    s = r["sampler"]
    if s["population"]:
        L += [f"<details><summary>Spot-check: {s['n']} random files to open</summary>", "",
              f"Picked at random from the {s['population']} hidden files (seed: the commit SHA, so anyone can re-pick them).", ""]
        L += [f"- `{'/'.join(p.split('/')[-2:])}`" for p in s["sample"]]
        L += ["", "</details>", ""]

    rej = r["judge"]["rejected"]
    if rej:
        L += [f"<details><summary>Made-up claims thrown out ({len(rej)})</summary>", "",
              "These accusations cite code that isn't in this PR, so nobody needs to read them:", ""]
        for v in rej:
            L.append(f"- \"{v['claim'][:90]}\": {v['why']}.")
        L += ["", "</details>", ""]

    L += ["<details><summary>Not checked</summary>", ""]
    L += [f"- {x['item']}: {x['why']}" for x in r["not_checked"]]
    L += ["", "</details>", ""]

    p = r["provenance"]
    L += ["<details><summary>How this review was made</summary>", "",
          f"- Diff: {r['change']['source']}, sha256 `{r['change']['diff_sha'][:12]}`",
          f"- Files sorted by: {cl['engine']}",
          f"- AI reviewer: {p['llm']}",
          f"- Rules: {rt['policy']}" + (f", sha256 `{p['policy_sha'][:12]}`" if p.get("policy_sha") else ""),
          f"- Settings: {p.get('settings', 'defaults')}",
          f"- Module trust: {p['trust']}",
          "", "</details>", "",
          "<sub>Earned-Trust PR Factory · AI reviews. Humans sign. Evidence decides.</sub>"]
    return "\n".join(L) + "\n"
