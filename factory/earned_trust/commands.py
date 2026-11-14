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


def load(run_dir: Path) -> dict:
    p = run_dir / "state.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"published_at": ledger.now(), "events": [], "spotcheck": None, "summary_disabled": False,
            "decisions": {}, "findings": {}, "verify": None, "signatures": [], "signed_complete": False}


def save(run_dir: Path, state: dict) -> None:
    (run_dir / "state.json").write_text(json.dumps(state, indent=1))


def gate(report: dict, state: dict) -> dict:
    missing = []
    if report["sampler"]["population"] and not state["spotcheck"]:
        missing.append("spot-check not answered")
    for a in report["abstentions"]:
        if a["id"] not in state["decisions"]:
            missing.append(f"{a['id']} not decided")
    for f in report["judge"]["accepted"]:
        if f["id"] not in state["findings"]:
            missing.append(f"{f['id']} neither accepted nor refuted")
    need = 2 if report["router"]["second_reviewer"] else 1
    if len(state["signatures"]) < need:
        missing.append(f"{need - len(state['signatures'])} signature(s) missing")
    return {"conclusion": "success" if not missing else "action_required", "missing": missing}


def apply(report: dict, run_dir: Path, actor: str, text: str, *, at: str | None = None,
          simulated: bool = False, can_sign: bool | None = None) -> tuple[dict, str]:
    """Runs one command. CAN_SIGN comes from GitHub (CODEOWNERS or write
    permission) when there is one; offline it is factory/owners.json."""
    state = load(run_dir)
    at = at or ledger.now()
    try:
        argv = shlex.split(text.strip())
    except ValueError as e:
        return state, f"Could not read the command: {e}"
    if not argv or not argv[0].startswith("/"):
        return state, "Not a command."
    cmd, args = argv[0][1:], argv[1:]
    ids_abs = {a["id"]: a for a in report["abstentions"]}
    ids_find = {f["id"]: f for f in report["judge"]["accepted"]}
    reply = ""
    if cmd == "spotcheck" and args and args[0] in ("clean", "escape"):
        state["spotcheck"] = {"result": args[0], "by": actor, "at": at, "sample": report["sampler"].get("sample", [])}
        if args[0] == "escape":
            state["summary_disabled"] = True
            reply = ("Escape recorded: summary mode is off for this PR, every hidden file is now yours to read, "
                     "and the classifier's escape is counted in the ledger.")
        else:
            reply = f"Spot-check clean ({report['sampler'].get('n', 0)} files)."
    elif cmd == "decide" and len(args) >= 3 and args[0] in ids_abs:
        a = ids_abs[args[0]]
        if args[1] not in a["options"]:
            return state, f"{args[0]} options are: {', '.join(a['options'])}"
        state["decisions"][args[0]] = {"option": args[1], "reason": " ".join(args[2:]), "by": actor, "at": at,
                                       "decision": a["decision"], "kind": a["kind"]}
        reply = f"{args[0]} decided by {actor}: {args[1]}."
    elif cmd == "accept" and args and args[0] in ids_find:
        state["findings"][args[0]] = {"verdict": "accepted", "by": actor, "at": at}
        reply = f"{args[0]} accepted: it goes into the receipt as a known issue."
    elif cmd == "refute" and len(args) >= 2 and args[0] in ids_find:
        state["findings"][args[0]] = {"verdict": "refuted", "evidence": " ".join(args[1:]), "by": actor, "at": at}
        reply = f"{args[0]} refuted by {actor}."
    elif cmd == "verify" and args:
        if report["router"]["tier"] != "T2":
            return state, "/verify is only asked on T2 changes."
        state["verify"] = {"answer": " ".join(args), "by": actor, "at": at}
        reply = "Comprehension answer recorded (optional, not graded)."
    elif cmd == "sign" and args:
        o = owners()
        allowed = can_sign if can_sign is not None else actor in o.get("owners", []) + o.get("second_reviewers", [])
        if not allowed:
            return state, f"{actor} is not an owner of this change (CODEOWNERS / write permission), so cannot sign."
        if any(s["by"] == actor for s in state["signatures"]):
            return state, f"{actor} has already signed."
        g = gate(report, {**state, "signatures": state["signatures"] + [{"by": actor}]})
        blocking = [m for m in g["missing"] if "signature" not in m]
        if blocking:
            return state, "Cannot sign yet: " + "; ".join(blocking)
        state["signatures"].append({"name": " ".join(args), "by": actor, "at": at})
        if gate(report, state)["conclusion"] == "success":
            state["signed_complete"] = True
            rc = receipt.build(report, state)
            receipt.write(rc, run_dir)
            state["receipt_hash"] = rc["hash"]
            reply = f"Signed by {' and '.join(s['name'] for s in state['signatures'])}. Receipt `{rc['hash'][:16]}`; the gate is green."
        else:
            reply = "Signature recorded; a second reviewer must sign too."
    else:
        return state, f"Unknown or incomplete command: {text.strip()}"
    state["events"].append({"at": at, "actor": actor, "command": text.strip(), "simulated": simulated})
    save(run_dir, state)
    return state, reply
