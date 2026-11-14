"""One OpenAI-compatible client for every LLM call: Vultr Serverless
Inference by default, a self-hosted vLLM on a Vultr Cloud GPU, or any
partner model, all by configuration:

    LLM_BASE_URL   e.g. https://api.vultrinference.com/v1
    LLM_API_KEY
    LLM_MODEL      no model name lives in the code: `python -m earned_trust models` lists them

Every call is cached under factory/cache/<branch>/llm/<input sha>.json with
the model, the prompt version and the hash of its input, so a run can be
replayed offline and audited later. If a call fails, the caller degrades to
deterministic-only and says so in the brief.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path


class LLMUnavailable(Exception):
    pass


def configured() -> bool:
    return bool(os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_MODEL"))


def _request(path: str, payload: dict | None = None, timeout: int = 120) -> dict:
    base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    if not base:
        raise LLMUnavailable("LLM_BASE_URL is not set")
    req = urllib.request.Request(base + path, method="POST" if payload is not None else "GET")
    req.add_header("Content-Type", "application/json")
    if os.environ.get("LLM_API_KEY"):
        req.add_header("Authorization", "Bearer " + os.environ["LLM_API_KEY"])
    data = json.dumps(payload).encode() if payload is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:  # network, HTTP, JSON: all mean "no LLM this run"
        raise LLMUnavailable(f"{type(e).__name__}: {e}") from e


def models() -> list[str]:
    return [m["id"] for m in _request("/models").get("data", [])]


def chat(system: str, user: str, *, prompt_version: str, cache_dir: Path, offline: bool) -> dict:
    """The model's answer and the record of the call. Offline, only a cached
    answer to the same input counts; otherwise LLMUnavailable."""
    model = os.environ.get("LLM_MODEL", "")
    key = hashlib.sha256(f"{prompt_version}\n{system}\n{user}".encode()).hexdigest()
    hit = None
    if cache_dir.exists():
        for p in sorted(cache_dir.glob(f"{key[:16]}*.json")):
            hit = json.loads(p.read_text())
            break
    if hit:
        return {**hit, "cached": True}
    if offline:
        raise LLMUnavailable("offline and no cached answer for this input")
    if not configured():
        raise LLMUnavailable("LLM_BASE_URL / LLM_MODEL not set")
    t0 = time.time()
    resp = _request("/chat/completions", {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    })
    content = resp["choices"][0]["message"]["content"]
    record = {
        "model": resp.get("model", model),
        "prompt_version": prompt_version,
        "input_sha256": key,
        "seconds": round(time.time() - t0, 2),
        "usage": resp.get("usage", {}),
        "content": content,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key[:16]}-{prompt_version}.json").write_text(json.dumps(record, indent=1))
    return {**record, "cached": False}


def extract_json(text: str):
    """The first JSON array or object in a model's answer."""
    for open_, close in (("[", "]"), ("{", "}")):
        a, b = text.find(open_), text.rfind(close)
        if a != -1 and b > a:
            try:
                return json.loads(text[a:b + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON in the model's answer")
