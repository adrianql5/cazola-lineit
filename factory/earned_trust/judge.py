"""Stage 4b: Deterministic Diff Judge.

The judge checks the citation, with code, before any accusation reaches a
human: the file is in the diff, the lines exist in it, at least one of them
is changed, and the symbol is written on them. Anything else is discarded
and logged as `hallucination_rejected`.

It does not judge whether the argument is right. An accepted accusation is
"citation verified", and a human still /accepts or /refutes it.
"""

from __future__ import annotations

from . import gitdiff

MAX_SPAN = 80


def _where(f: gitdiff.FileDiff, symbol: str) -> list[int]:
    return [l.new_no or l.old_no for h in f.hunks for l in h.lines if symbol in l.text][:5]


def verdict(acc: dict, files: list[gitdiff.FileDiff]) -> dict:
    def reject(why: str, **extra) -> dict:
        return {**acc, "verdict": "REJECTED", "kind": "hallucination_rejected", "why": why, **extra}

    symbol = (acc.get("symbol") or "").strip()
    if not symbol:
        return reject("names no symbol, so nothing on the cited lines can confirm it")
    if not acc.get("file"):
        anywhere = [f.path for f in files if _where(f, symbol)]
        if anywhere:
            return reject(f"cites no file or line; `{symbol}` does appear in {anywhere[0]}, so the claim could be re-asked with a citation")
        return reject(f"cites no file or line, and `{symbol}` appears nowhere in the diff")
    f = gitdiff.find(files, acc["file"])
    if f is None:
        return reject(f"{acc['file']} is not in this diff")
    a, b = acc.get("line_start"), acc.get("line_end") or acc.get("line_start")
    if not isinstance(a, int) or not isinstance(b, int):
        return reject("no line range")
    if b < a or b - a > MAX_SPAN:
        return reject(f"line range {a}-{b} is empty or wider than {MAX_SPAN} lines")
    side = acc.get("side", "new")
    get = f.new_line if side == "new" else f.old_line
    shown = [(n, get(n)) for n in range(a, b + 1)]
    present = [(n, l) for n, l in shown if l is not None]
    if not present:
        return reject(f"lines {a}-{b} of {f.path} are not in the diff", symbol_found_at=_where(f, symbol))
    if not any(l.kind != " " for _, l in present):
        return reject(f"lines {a}-{b} are unchanged context: the accusation is not about this change", symbol_found_at=_where(f, symbol))
    if not any(symbol in l.text for _, l in present):
        return reject(f"`{symbol}` is not on lines {a}-{b} of {f.path}", symbol_found_at=_where(f, symbol))
    evidence = [{"line": n, "kind": l.kind, "text": l.text.rstrip()} for n, l in present]
    return {**acc, "file": f.path, "verdict": "ACCEPTED", "kind": "citation_verified",
            "why": f"`{symbol}` is on a changed line of {f.path}:{a}-{b}", "evidence": evidence}


def run(accusations: list[dict], files: list[gitdiff.FileDiff]) -> dict:
    out = [verdict(a, files) for a in accusations]
    acc = [v for v in out if v["verdict"] == "ACCEPTED"]
    rej = [v for v in out if v["verdict"] == "REJECTED"]
    return {"stage": "judge", "accepted": acc, "rejected": rej,
            "total": len(out), "rejection_rate": round(len(rej) / len(out), 3) if out else None}
