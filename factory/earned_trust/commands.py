"""Slash commands on the PR (issue_comment) and the gate they open.

    /spotcheck clean "<a line from one sample file>" | /spotcheck escape "<what looks wrong>"
    /decide <ABS-id> <option> "<reason>"
    /accept <finding-id> | /accept all
    /refute <finding-id> "<evidence>"
    /verify "<answer>"            (T2 only, optional)
    /sign "<Full Name>"

State lives in runs/<branch>/state.json; every command is an event with a
timestamp, who sent it, and whether it was a simulated session.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from . import ledger, receipt
from .sources import FACTORY


def owners() -> dict:
    p = FACTORY / "owners.json"
    return json.loads(p.read_text()) if p.exists() else {"owners": [], "second_reviewers": []}


def load_empty() -> dict:
    return {"published_at": ledger.now(), "events": [], "spotcheck": None, "summary_disabled": False,
            "decisions": {}, "findings": {}, "verify": None, "signatures": [], "signed_complete": False}


def load(run_dir: Path) -> dict:
    p = run_dir / "state.json"
    return json.loads(p.read_text()) if p.exists() else load_empty()


def save(run_dir: Path, state: dict) -> None:
    (run_dir / "state.json").write_text(json.dumps(state, indent=1))


def explain(report: dict, ident: str) -> str:
    """A longer answer about one finding, decision or claim. Changes nothing."""
    ids = ([f["id"] for f in report["judge"]["accepted"]] + [a["id"] for a in report["abstentions"]]
           + [c["id"] for c in report["tracer"]["claims"]])
    if not ident:
        return f"Say what to explain: `/explain <id>`. Ids on this PR: {', '.join(ids)}."
    f = next((x for x in report["judge"]["accepted"] if x["id"] == ident), None)
    if f:
        L = [f"**{f['id']}** · `{f['file']}:{f['line_start']}`", "", f["claim"], ""]
        ev = f.get("evidence", [])
        if ev:
            L += ["```diff"] + [f"{e['kind']}{e['text']}" for e in ev] + ["```", ""]
        src = f["source"]
        how = ("a fixed rule that looks for this pattern in every diff" if "rules" in src or "auditor" in src
               else f"the AI reviewer ({src})")
        L += [f"**Who raised it:** {how}. A plain-code check confirmed that `{f['symbol']}` is on that changed line, "
              "so the finding points at real code. Whether it is a real problem is your call."]
        if f.get("also_raised_by"):
            L.append(f"Also raised by: {', '.join(f['also_raised_by'])}.")
        L += ["", f'**Answer:** `/accept {f["id"]}` if it is real, or `/refute {f["id"]} "why"` if not.']
        return "\n".join(L)
    a = next((x for x in report["abstentions"] if x["id"] == ident), None)
    if a:
        opts = " or ".join(f'`/decide {a["id"]} {o} "why"`' for o in a["options"])
        return "\n".join([f"**{a['id']}** · {a['decision']}", "",
                          f"**Why the AI won't decide:** {a['why_not_ai']}",
                          f"**Who usually decides:** {a['who_decides']}.",
                          f"**What would help:** {'; '.join(a['missing_evidence'])}.",
                          f"**Where:** `{a['cite']}`", "", f"**Answer:** {opts}."])
    c = next((x for x in report["tracer"]["claims"] if x["id"] == ident), None)
    if c:
        impl = ", ".join(f"`{i['file']}:{i['line']}`" for i in c["implementation"][:3]) or "none found"
        tests = ", ".join(f"`{t['test']}`" for t in c["tests"][:5]) or "none"
        return "\n".join([f"**{c['id']}** · {c['claim']}", "", f"**Status:** {c['status'].lower()}: {c['why']}.",
                          f"**Code:** {impl}", f"**Tests that mention it:** {tests}",
                          f"**Tests ran:** {c['execution']}"])
    return f"There is nothing called `{ident}` on this PR. Ids here: {', '.join(ids)}."


def todo(report: dict, state: dict) -> list[dict]:
    """What is left before the PR can merge: each item says what and how."""
    out = []
    tr = report["tracer"]
    rs = tr.get("requirements_status", "written")
    if rs in ("missing", "proposed") and not state.get("requirements"):
        if rs == "proposed":
            out.append({"what": "Check the requirements the AI proposed",
                        "how": 'compare them with the issue, then reply `/requirements ok`, or `/requirements wrong "what is missing"`'})
        else:
            out.append({"what": "Say what this PR must do",
                        "how": 'no requirements are written for this issue, so only the change\'s own claims were checked. '
                               'Compare the change with the issue, then reply `/requirements ok "what you checked"`'})
    s = report["sampler"]
    if s["population"] and not state["spotcheck"]:
        out.append({"what": f"Spot-check {s['n']} sample file{'' if s['n'] == 1 else 's'}",
                    "how": f"open {'it' if s['n'] == 1 else 'them'} (list below), then reply "
                           '`/spotcheck clean "<copy one line from any of them>"`, or `/spotcheck escape "<what looks wrong>"`'})
    for a in report["abstentions"]:
        if a["id"] not in state["decisions"]:
            opts = " or ".join(f'`/decide {a["id"]} {o} "why"`' for o in a["options"])
            out.append({"what": f"Decide {a['id']}", "how": f"{a['decision']} Reply {opts}"})
    open_ = [f["id"] for f in report["judge"]["accepted"] if f["id"] not in state["findings"]]
    if open_:
        out.append({"what": f"Answer {'finding' if len(open_) == 1 else 'findings'} {', '.join(open_)}",
                    "how": 'reply `/accept <id>` for each one that is real (`/accept all` for every one left), '
                           'or `/refute <id> "why"` if it is not'})
    need, groups = required_signatures(report)
    signers = {x["by"] for x in state["signatures"]}
    missing = [g for g in groups if not signers & set(g["owners"])]
    for g in missing:
        out.append({"what": f"Signature from an owner of {g['zone']} ({owners_text(g['owners'])})",
                    "how": f'{owners_text(g["owners"])} replies `/sign "Full Name"`'})
    extra = need - len(state["signatures"]) - len(missing)
    if extra > 0:
        if need == 1:
            what = "Signature from an owner"
        elif state["signatures"] or missing:
            what = f"{extra} more signature{'s' if extra > 1 else ''} (each from a different person)"
        else:
            what = f"{need} signatures, each from a different person"
        out.append({"what": what, "how": 'reply `/sign "Your Full Name"`'})
    return out


def owners_text(owners: list[str]) -> str:
    return " or ".join(f"@{o}" for o in owners)


def required_signatures(report: dict) -> tuple[int, list[dict]]:
    """How many distinct signatures, and for each critical area with owners,
    one signature that must come from one of them."""
    sens = report.get("sensitivity") or {"required": {"signatures": 1, "owner_groups": []}}
    need = max(2 if report["router"]["second_reviewer"] else 1, sens["required"]["signatures"])
    return need, sens["required"]["owner_groups"]


def gate(report: dict, state: dict) -> dict:
    items = todo(report, state)
    return {"conclusion": "success" if not items else "action_required",
            "missing": [i["what"] for i in items], "todo": items}


USAGE = {
    "requirements": '`/requirements ok "what you checked"` or `/requirements wrong "what is missing"`',
    "explain": "`/explain <id>` (a finding, a decision or a claim)",
    "spotcheck": '`/spotcheck clean "<a line from one sample file>"` or `/spotcheck escape "<what looks wrong>"`',
    "decide": '`/decide ABS-1 <option> "why"`',
    "accept": "`/accept <finding-id>` or `/accept all`",
    "refute": '`/refute <finding-id> "why"`',
    "verify": '`/verify "your answer"`',
    "sign": '`/sign "Your Full Name"`',
}


def apply(report: dict, run_dir: Path, actor: str, text: str, *, at: str | None = None,
          simulated: bool = False, can_sign: bool | None = None) -> tuple[dict, str]:
    """Runs one command and returns a short reply. When a command can't run,
    the reply says why and what to type instead. CAN_SIGN comes from GitHub
    (write access) when there is one; offline it is factory/owners.json."""
    state = load(run_dir)
    at = at or ledger.now()
    try:
        argv = shlex.split(text.strip())
    except ValueError:
        return state, ("Couldn't read that command: a quote is not closed. "
                       'Put the reason in quotes, like `/decide ABS-1 keep-guard "the docs say so"`.')
    if not argv or not argv[0].startswith("/"):
        return state, "Not a command. Commands start with `/`."
    cmd, args = argv[0][1:].lower(), argv[1:]
    ids_abs = {a["id"]: a for a in report["abstentions"]}
    ids_find = {f["id"]: f for f in report["judge"]["accepted"]}
    finds = ", ".join(ids_find) or "none"

    def bad_finding(fid: str) -> str:
        return f"There is no finding `{fid}` on this PR. Findings here: {finds}."

    if cmd not in USAGE:
        return state, f"I don't know `/{cmd}`. Commands: " + ", ".join(f"`/{c}`" for c in USAGE) + "."
    if cmd == "requirements":
        rs = report["tracer"].get("requirements_status", "written")
        if rs == "written":
            return state, "This PR's requirements are already written down, so there is nothing to confirm."
        if rs == "not needed":
            return state, "This PR changes documentation only, so there are no requirements to confirm."
        if not args or args[0] not in ("ok", "wrong"):
            return state, f"Say whether they are right: {USAGE['requirements']}."
        if args[0] == "wrong" and len(args) < 2:
            return state, 'Say what is missing or wrong: `/requirements wrong "what is missing"`.'
        state["requirements"] = {"verdict": args[0], "note": " ".join(args[1:]), "by": actor, "at": at}
        state["events"].append({"at": at, "actor": actor, "command": text.strip(), "simulated": simulated})
        save(run_dir, state)
        return state, ("Requirements confirmed." if args[0] == "ok"
                       else "Noted. The receipt will say the requirements were incomplete, and why.")
    if cmd == "explain":
        return state, explain(report, args[0] if args else "")
    if cmd == "spotcheck":
        if not args or args[0] not in ("clean", "escape"):
            return state, f"Say how the sample looked: {USAGE['spotcheck']}."
        if not report["sampler"]["population"]:
            return state, "Nothing was hidden on this PR, so there is nothing to spot-check."
        quote = " ".join(args[1:])
        opened = None
        if args[0] == "clean":
            if not quote:
                return state, ('Copy one line from any of the sample files, to show you opened it: '
                               '`/spotcheck clean "<the line>"`.')
            q = "".join(quote.split())
            proof = report["sampler"].get("proof_lines", {})
            if len(q) < 8:
                return state, 'That quote is too short to show anything. Copy a whole line, or a class or method name from it.'
            opened = next((p for p, lines in proof.items() if any(q in t or (len(q) >= 12 and t in q) for t in lines)), None)
            if not opened:
                return state, ("That line doesn't show which sample file you opened: it isn't in them, or almost every "
                               "hidden file has it (like the new attribute). Copy a line that only one of the sample "
                               "files has; a class or method name works well.")
        elif not quote:
            return state, 'Say what looks wrong, so it can be fixed: `/spotcheck escape "<what looks wrong>"`.'
        state["spotcheck"] = {"result": args[0], "by": actor, "at": at, "sample": report["sampler"].get("sample", []),
                              "quote": quote, "opened": opened}
        if args[0] == "escape":
            state["summary_disabled"] = True
            reply = "Thanks. Summary mode is now off for this PR: please read every file. The miss is recorded."
        else:
            reply = f"Spot-check done ({report['sampler'].get('n', 0)} files)."
    elif cmd == "decide":
        if not args or args[0] not in ids_abs:
            have = ", ".join(ids_abs) or "none"
            return state, f"There is no decision `{args[0] if args else ''}` on this PR. Decisions here: {have}."
        a = ids_abs[args[0]]
        if len(args) < 2 or args[1] not in a["options"]:
            return state, f"{a['id']} options: " + " or ".join(f"`{o}`" for o in a["options"]) + \
                f'. Example: `/decide {a["id"]} {a["options"][0]} "why"`.'
        if len(args) < 3:
            return state, f'Add your reason in quotes: `/decide {a["id"]} {args[1]} "why"`.'
        state["decisions"][args[0]] = {"option": args[1], "reason": " ".join(args[2:]), "by": actor, "at": at,
                                       "decision": a["decision"], "kind": a["kind"]}
        reply = f"{args[0]}: `{args[1]}`, decided by @{actor}."
    elif cmd == "accept" and args and args[0].lower() == "all":
        # every finding not answered yet; a /refute already given stays
        left = [fid for fid in ids_find if fid not in state["findings"]]
        if not left:
            return state, "Every finding on this PR is already answered." if ids_find else "There are no findings on this PR."
        for fid in left:
            state["findings"][fid] = {"verdict": "accepted", "by": actor, "at": at}
        reply = f"{', '.join(left)} accepted. " + ("It goes in the receipt as a known issue." if len(left) == 1
                                                  else "They go in the receipt as known issues.")
    elif cmd == "accept":
        if not args or args[0] not in ids_find:
            return state, bad_finding(args[0] if args else "")
        state["findings"][args[0]] = {"verdict": "accepted", "by": actor, "at": at}
        reply = f"{args[0]} accepted. It goes in the receipt as a known issue."
    elif cmd == "refute":
        if not args or args[0] not in ids_find:
            return state, bad_finding(args[0] if args else "")
        if len(args) < 2:
            return state, f'Say why it is wrong: `/refute {args[0]} "why"`.'
        state["findings"][args[0]] = {"verdict": "refuted", "evidence": " ".join(args[1:]), "by": actor, "at": at}
        reply = f"{args[0]} refuted by @{actor}."
    elif cmd == "verify":
        if report["router"]["tier"] != "T2":
            return state, "`/verify` is only for changes that need a full read (T2)."
        if not args:
            return state, f"Write your answer: {USAGE['verify']}."
        state["verify"] = {"answer": " ".join(args), "by": actor, "at": at}
        reply = "Answer saved (optional, not graded)."
    else:  # sign
        if not args:
            return state, f"Sign with your full name: {USAGE['sign']}."
        o = owners()
        allowed = can_sign if can_sign is not None else actor in o.get("owners", []) + o.get("second_reviewers", [])
        if not allowed:
            return state, (f"@{actor} can't sign: only people with write access to this repository can. "
                           "Ask a maintainer to sign.")
        if any(x["by"] == actor for x in state["signatures"]):
            return state, f"@{actor} has already signed."
        _, groups = required_signatures(report)
        allowed_owners = sorted({o for g in groups for o in g["owners"]})
        if allowed_owners and actor not in allowed_owners:
            areas = ", ".join(sorted({g["zone"] for g in groups}))
            return state, (f"@{actor} can't sign: this change touches a critical area ({areas}), and only its owners "
                           f"can sign it: {owners_text(allowed_owners)}. Ask one of them to review and sign.")
        left = [i for i in todo(report, {**state, "signatures": state["signatures"] + [{"by": actor}]})
                if not i["what"].startswith("Signature")]
        if left:
            return state, "You can't sign yet. Still to do:\n" + "\n".join(f"- {i['what']} → {i['how']}" for i in left)
        state["signatures"].append({"name": " ".join(args), "by": actor, "at": at})
        if gate(report, state)["conclusion"] == "success":
            state["signed_complete"] = True
            rc = receipt.build(report, state)
            receipt.write(rc, run_dir)
            state["receipt_hash"] = rc["hash"]
            reply = f"Signed by {' and '.join(x['name'] for x in state['signatures'])}. The check is green; the receipt is attached to it."
        else:
            reply = "Signature saved. A second owner must sign too."
    state["events"].append({"at": at, "actor": actor, "command": text.strip(), "simulated": simulated})
    save(run_dir, state)
    return state, reply
