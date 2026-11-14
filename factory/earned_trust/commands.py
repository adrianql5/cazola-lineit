"""Slash commands on the PR (issue_comment) and the gate they open.

    /spotcheck clean|escape
    /decide <ABS-id> <option> "<reason>"
    /accept <finding-id>
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


def todo(report: dict, state: dict) -> list[dict]:
    """What is left before the PR can merge: each item says what and how."""
    out = []
    s = report["sampler"]
    if s["population"] and not state["spotcheck"]:
        out.append({"what": f"Spot-check {s['n']} sample files",
                    "how": "open them, then reply `/spotcheck clean` (or `/spotcheck escape` if one looks wrong)"})
    for a in report["abstentions"]:
        if a["id"] not in state["decisions"]:
            opts = " or ".join(f'`/decide {a["id"]} {o} "why"`' for o in a["options"])
            out.append({"what": f"Decide {a['id']} (see *Your call*)", "how": f"reply {opts}"})
    open_ = [f["id"] for f in report["judge"]["accepted"] if f["id"] not in state["findings"]]
    if open_:
        out.append({"what": f"Answer {'finding' if len(open_) == 1 else 'findings'} {', '.join(open_)}",
                    "how": 'reply `/accept <id>` for each one that is real, or `/refute <id> "why"` if it is not'})
    need = 2 if report["router"]["second_reviewer"] else 1
    if len(state["signatures"]) < need:
        who = "an owner" if need - len(state["signatures"]) == 1 and need == 1 else "a second owner"
        out.append({"what": f"Signature from {who}", "how": 'reply `/sign "Your Full Name"`'})
    return out


def gate(report: dict, state: dict) -> dict:
    items = todo(report, state)
    return {"conclusion": "success" if not items else "action_required",
            "missing": [i["what"] for i in items], "todo": items}


USAGE = {
    "spotcheck": "`/spotcheck clean` or `/spotcheck escape`",
    "decide": '`/decide ABS-1 <option> "why"`',
    "accept": "`/accept <finding-id>`",
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
    if cmd == "spotcheck":
        if not args or args[0] not in ("clean", "escape"):
            return state, f"Say how the sample looked: {USAGE['spotcheck']}."
        if not report["sampler"]["population"]:
            return state, "Nothing was hidden on this PR, so there is nothing to spot-check."
        state["spotcheck"] = {"result": args[0], "by": actor, "at": at, "sample": report["sampler"].get("sample", [])}
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
