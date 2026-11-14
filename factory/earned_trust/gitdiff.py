"""Unified diffs, parsed into files, hunks and numbered lines.

Every other stage cites code as (file, line) pairs taken from here, and the
Deterministic Diff Judge checks citations against the same structure, so
there is one source of truth for "what lines does this change contain".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


@dataclass
class Line:
    kind: str  # "+", "-" or " "
    text: str
    old_no: int | None
    new_no: int | None


@dataclass
class Hunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    header: str
    lines: list[Line] = field(default_factory=list)

    @property
    def added(self) -> list[Line]:
        return [l for l in self.lines if l.kind == "+"]

    @property
    def deleted(self) -> list[Line]:
        return [l for l in self.lines if l.kind == "-"]


@dataclass
class FileDiff:
    path: str
    old_path: str | None
    status: str  # added, modified, deleted, renamed
    hunks: list[Hunk] = field(default_factory=list)
    binary: bool = False

    @property
    def added(self) -> int:
        return sum(len(h.added) for h in self.hunks)

    @property
    def deleted(self) -> int:
        return sum(len(h.deleted) for h in self.hunks)

    @property
    def changed(self) -> int:
        return self.added + self.deleted

    def added_lines(self) -> list[Line]:
        return [l for h in self.hunks for l in h.added]

    def deleted_lines(self) -> list[Line]:
        return [l for h in self.hunks for l in h.deleted]

    def new_line(self, n: int) -> Line | None:
        """The line numbered N in the new file, if the diff shows it."""
        for h in self.hunks:
            for l in h.lines:
                if l.new_no == n:
                    return l
        return None

    def old_line(self, n: int) -> Line | None:
        for h in self.hunks:
            for l in h.lines:
                if l.old_no == n and l.kind != "+":
                    return l
        return None


def parse(text: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    cur: FileDiff | None = None
    hunk: Hunk | None = None
    old_no = new_no = 0
    for raw in text.split("\n"):
        if raw.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*) b/(.*)$", raw)
            path = m.group(2) if m else raw.split(" ")[-1]
            cur = FileDiff(path=path, old_path=m.group(1) if m else None, status="modified")
            files.append(cur)
            hunk = None
            continue
        if cur is None:
            continue
        if raw.startswith("new file mode"):
            cur.status = "added"
            continue
        if raw.startswith("deleted file mode"):
            cur.status = "deleted"
            continue
        if raw.startswith("rename from "):
            cur.status = "renamed"
            cur.old_path = raw[len("rename from "):]
            continue
        if raw.startswith("Binary files"):
            cur.binary = True
            continue
        m = HUNK_RE.match(raw)
        if m:
            hunk = Hunk(
                old_start=int(m.group(1)),
                old_len=int(m.group(2) or 1),
                new_start=int(m.group(3)),
                new_len=int(m.group(4) or 1),
                header=m.group(5).strip(),
            )
            cur.hunks.append(hunk)
            old_no, new_no = hunk.old_start, hunk.new_start
            continue
        if hunk is None:
            continue  # index, ---, +++ lines before the first hunk
        if raw.startswith("+"):
            hunk.lines.append(Line("+", raw[1:], None, new_no))
            new_no += 1
        elif raw.startswith("-"):
            hunk.lines.append(Line("-", raw[1:], old_no, None))
            old_no += 1
        elif raw.startswith(" "):
            hunk.lines.append(Line(" ", raw[1:], old_no, new_no))
            old_no += 1
            new_no += 1
        elif raw.startswith("\\"):
            continue  # "\ No newline at end of file"
    return files


def find(files: list[FileDiff], path: str) -> FileDiff | None:
    """The file at PATH, or the only one whose path ends with it."""
    for f in files:
        if f.path == path:
            return f
    tail = [f for f in files if f.path.endswith("/" + path.lstrip("/"))]
    return tail[0] if len(tail) == 1 else None
