"""Per-repository settings: `.sancho.toml` at the root of the repository.

In GitHub Actions it is read from the pull request's *base* branch, never
from the pull request itself, so a change cannot loosen the rules it is
reviewed by. Without the file, the defaults below apply: they are the
settings written for MessagePack-CSharp, the repository of the challenge.

    [gate]
    merge_on_sign = false      # merge the PR as soon as the gate turns green
    merge_method = "merge"     # merge | squash | rebase

    [review]
    sample_rate = 0.05                                   # share of hidden files a person spot-checks
    generated = ['^tests/.*/Resources/.*\\.g\\.cs$']     # generated files, checked as a pattern
    tests = ['^tests/', '(^|/)tests?/']                  # test code
    public_api = ['^src/MessagePack(\\.Annotations)?/']  # published packages: a new `public` forces a full read
    source = ['^src/']                                   # where unsafe code, severities and wire-format changes count
    analyzer_releases = ['AnalyzerReleases\\.(Un)?[Ss]hipped\\.md$']
    test_projects = ['^tests/.*\\.csproj$']              # test project files: excluded tests force a full read

    [sensitivity]
    detectors = ["money", "security", "data", "untrusted-input"]   # built in; they can only raise the review level
    extra = []          # your own: [{ name = "...", pattern = "regex", why = "..." }]
    ai = true           # also ask the AI which changed lines are sensitive (judge-checked, can only raise)

    [[critical]]        # a critical area: always a full read, signed by its owners
    name = "payments"
    paths = ['^src/payments/']
    owners = ["ana", "luis"]   # GitHub logins; empty = the file's owners in CODEOWNERS
    signatures = 2             # distinct signatures needed
"""

from __future__ import annotations

import copy
import hashlib
import os
import tomllib
from pathlib import Path

FILE = ".sancho.toml"

DEFAULTS: dict = {
    "gate": {"merge_on_sign": False, "merge_method": "merge"},
    "review": {
        "sample_rate": 0.05,
        "generated": [r"^tests/.*/Resources/.*\.g\.cs$"],
        "tests": [r"^tests/", r"(^|/)tests?/"],
        "public_api": [r"^src/MessagePack(\.Annotations)?/"],
        "source": [r"^src/"],
        "analyzer_releases": [r"AnalyzerReleases\.(Un)?[Ss]hipped\.md$"],
        "test_projects": [r"^tests/.*\.csproj$"],
    },
    "sensitivity": {"detectors": ["money", "security", "data", "untrusted-input"], "extra": [], "ai": True},
    "critical": [],
    # The folder trust learned from git history comes from MessagePack-CSharp's
    # history. "auto": used only with these defaults (no settings file), which are
    # MessagePack's too; "on" / "off" force it.
    "trust": {"upstream_history": "auto"},
}

CRITICAL_KEYS = {"name": str, "paths": list, "owners": list, "signatures": int}
EXTRA_KEYS = {"name": str, "pattern": str, "why": str}

_current: dict = copy.deepcopy(DEFAULTS)
_source = "defaults (written for MessagePack-CSharp)"
_text = ""
_codeowners = ""


def parse(text: str) -> dict:
    """The settings in TEXT over the defaults. An unknown key is an error,
    so a typo does not silently fall back to a default."""
    data = tomllib.loads(text)
    cfg = copy.deepcopy(DEFAULTS)
    for i, area in enumerate(data.pop("critical", [])):
        unknown = set(area) - set(CRITICAL_KEYS)
        if unknown:
            raise ValueError(f"{FILE}: unknown setting critical.{sorted(unknown)[0]}; known: {', '.join(CRITICAL_KEYS)}")
        if not area.get("name") or not area.get("paths"):
            raise ValueError(f"{FILE}: critical area {i + 1} needs a name and paths")
        for key, kind in CRITICAL_KEYS.items():
            if key in area and type(area[key]) is not kind:
                raise ValueError(f"{FILE}: critical.{key} must be {kind.__name__}")
        cfg["critical"].append({"name": area["name"], "paths": area["paths"], "owners": area.get("owners", []),
                                "signatures": max(1, area.get("signatures", 1))})
    for section, values in data.items():
        if section not in cfg:
            raise ValueError(f"{FILE}: unknown section [{section}]; known: {', '.join(cfg)}")
        for key, value in values.items():
            if key not in cfg[section]:
                raise ValueError(f"{FILE}: unknown setting {section}.{key}; known: {', '.join(cfg[section])}")
            if type(value) is not type(cfg[section][key]):
                raise ValueError(f"{FILE}: {section}.{key} must be {type(cfg[section][key]).__name__}")
            cfg[section][key] = value
    for x in cfg["sensitivity"]["extra"]:
        if set(x) - set(EXTRA_KEYS) or not x.get("name") or not x.get("pattern"):
            raise ValueError(f"{FILE}: each sensitivity.extra needs name and pattern (and optionally why)")
    if cfg["trust"]["upstream_history"] not in ("auto", "on", "off"):
        raise ValueError(f"{FILE}: trust.upstream_history must be auto, on or off")
    if cfg["gate"]["merge_method"] not in ("merge", "squash", "rebase"):
        raise ValueError(f"{FILE}: gate.merge_method must be merge, squash or rebase")
    return cfg


def use(text: str | None, source: str, codeowners: str | None = None) -> dict:
    """Make TEXT (or the defaults, if None) the settings of this run, and
    CODEOWNERS the repository's code owners file, if it has one."""
    global _current, _source, _text, _codeowners
    _current = parse(text) if text else copy.deepcopy(DEFAULTS)
    _source = source if text else "defaults (written for MessagePack-CSharp)"
    _text = text or ""
    _codeowners = codeowners or ""
    return _current


def codeowners() -> str:
    return _codeowners


def load_local(root: Path | None = None) -> dict:
    """Outside GitHub: SANCHO_CONFIG, or .sancho.toml in ROOT, or the defaults."""
    path = Path(os.environ["SANCHO_CONFIG"]) if os.environ.get("SANCHO_CONFIG") else (root / FILE if root else None)
    if path and path.exists():
        return use(path.read_text(), str(path))
    return use(None, "")


def get() -> dict:
    return _current


def source() -> str:
    return _source


def upstream_history() -> bool:
    """Whether MessagePack-CSharp's git history sets the folders' trust."""
    v = _current["trust"]["upstream_history"]
    return not _text if v == "auto" else v == "on"


def digest() -> str:
    """Pinned in the receipt with the rules' code: the settings that let a change through."""
    return hashlib.sha256((_text + "\n" + _codeowners).encode()).hexdigest()
