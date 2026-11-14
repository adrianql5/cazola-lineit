"""Where a change comes from: the cached replay of a branch (offline), the
MessagePack clone itself (online), or a seeded mutation of either."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import gitdiff

FACTORY = Path(__file__).resolve().parent.parent
CACHE = FACTORY / "cache"
DEFAULT_REPO = FACTORY.parent.parent / "junction26-messagepack-csharp"


@dataclass
class Change:
    branch: str
    issue: int
    sha: str
    subject: str
    author: str
    diff_text: str
    issue_title: str
    issue_body: str
    issue_url: str
    source: str
    files: list[gitdiff.FileDiff] = field(default_factory=list)

    @property
    def diff_sha(self) -> str:
        return hashlib.sha256(self.diff_text.encode()).hexdigest()

    @property
    def added(self) -> int:
        return sum(f.added for f in self.files)

    @property
    def deleted(self) -> int:
        return sum(f.deleted for f in self.files)


def branches() -> list[str]:
    return sorted(p.name for p in CACHE.iterdir() if p.is_dir() and (p / "diff.patch").exists())


def load(branch: str, offline: bool = True, repo: str | None = None) -> Change:
    d = CACHE / branch
    commit = json.loads((d / "commit.json").read_text())
    issue = json.loads((d / "issue.json").read_text())
    if offline:
        text, source = (d / "diff.patch").read_text(), "replay cache (factory/cache)"
    else:
        repo = repo or os.environ.get("ET_REPO") or str(DEFAULT_REPO)
        ref = f"origin/{branch}"
        text = subprocess.run(
            ["git", "-C", repo, "diff", "--no-color", "--no-ext-diff", f"{ref}~1", ref],
            check=True, capture_output=True, text=True,
        ).stdout
        commit["sha"] = subprocess.run(
            ["git", "-C", repo, "rev-parse", ref], check=True, capture_output=True, text=True
        ).stdout.strip()
        source = f"git ({repo})"
    return make(branch, commit, issue, text, source)


def make(branch: str, commit: dict, issue: dict, text: str, source: str) -> Change:
    return Change(
        branch=branch,
        issue=int(commit["issue"]),
        sha=commit["sha"],
        subject=commit["subject"],
        author=commit["author"],
        diff_text=text,
        issue_title=issue.get("title", ""),
        issue_body=issue.get("body", ""),
        issue_url=issue.get("url", ""),
        source=source,
        files=gitdiff.parse(text),
    )
