"""Sets up the merge gate on a repository with one command, instead of by
hand in Settings: a branch ruleset that makes the default branch (and any
other branch named) take changes only through pull requests, and only once
the check `earned-trust/human-accountability-gate` is green, which happens
when an owner signs. Running it again changes nothing if the ruleset is
already right; a ruleset that requires the same check is updated in place.

Needs a token with admin rights on the repository (GitHub Actions' own
token cannot manage rulesets), so it is run once by an owner:

    python3 factory/et.py protect --repo owner/name [--branch ju26-base] [--dry-run]
"""

from __future__ import annotations

import json
import os
import subprocess

from . import github

NAME = "Earned-Trust gate"
GITHUB_ACTIONS_APP = 15368  # the check must come from GitHub Actions, not from any other app or token


def ruleset(branches: list[str]) -> dict:
    return {
        "name": NAME,
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"] + [f"refs/heads/{b}" for b in branches], "exclude": []}},
        "bypass_actors": [],  # nobody merges around the gate, admins included
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": 0,  # the signature is the approval
                "dismiss_stale_reviews_on_push": False,
                "require_code_owner_review": False,
                "require_last_push_approval": False,
                "required_review_thread_resolution": False,
            }},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": False,
                "do_not_enforce_on_create": False,
                "required_status_checks": [{"context": github.CHECK, "integration_id": GITHUB_ACTIONS_APP}],
            }},
        ],
    }


def ours(rs: dict) -> bool:
    """A ruleset we manage: ours by name, or one that already requires the gate check."""
    if rs.get("name") == NAME:
        return True
    for rule in rs.get("rules", []):
        if rule.get("type") == "required_status_checks":
            if any(c.get("context") == github.CHECK for c in rule["parameters"].get("required_status_checks", [])):
                return True
    return False


def token() -> str:
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit("No token: set GITHUB_TOKEN, or log in with `gh auth login` as an admin of the repository.")


def main(repo: str, branches: list[str], dry_run: bool = False) -> dict:
    want = ruleset(branches)
    if dry_run:
        print(json.dumps(want, indent=1))
        return {"action": "dry-run", "ruleset": want}
    os.environ["GITHUB_TOKEN"] = token()
    try:
        existing = github.gh("GET", f"/repos/{repo}/rulesets")
    except Exception as e:
        raise SystemExit(f"Could not read the rulesets of {repo} ({e}). The token needs admin rights on the repository.")
    # the list has no rules in it: read each ruleset in full before deciding it is ours
    match = [r for r in existing if r.get("name") == NAME]
    if not match:
        full = [github.gh("GET", f"/repos/{repo}/rulesets/{r['id']}") for r in existing]
        match = [r for r in full if ours(r)]
    if match:
        rid = match[0]["id"]
        github.gh("PUT", f"/repos/{repo}/rulesets/{rid}", want)
        action = f"updated ruleset {rid} (was \"{match[0]['name']}\")"
    else:
        rid = github.gh("POST", f"/repos/{repo}/rulesets", want)["id"]
        action = f"created ruleset {rid}"
    covered = ", ".join(["the default branch"] + branches)
    print(f"{repo}: {action}. {covered}: changes only through pull requests, merged once "
          f"`{github.CHECK}` is green (an owner signed). No bypass, admins included.")
    return {"action": action, "id": rid, "ruleset": want}
