"""Per-repository settings: `.earned-trust.toml` at the root of the repository.

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
"""

from __future__ import annotations

import copy
import hashlib
import os
import tomllib
from pathlib import Path

FILE = ".earned-trust.toml"

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
}

_current: dict = copy.deepcopy(DEFAULTS)
_source = "defaults (written for MessagePack-CSharp)"
_text = ""


def parse(text: str) -> dict:
    """The settings in TEXT over the defaults. An unknown key is an error,
    so a typo does not silently fall back to a default."""
    data = tomllib.loads(text)
    cfg = copy.deepcopy(DEFAULTS)
    for section, values in data.items():
        if section not in cfg:
            raise ValueError(f"{FILE}: unknown section [{section}]; known: {', '.join(cfg)}")
        for key, value in values.items():
            if key not in cfg[section]:
                raise ValueError(f"{FILE}: unknown setting {section}.{key}; known: {', '.join(cfg[section])}")
            if type(value) is not type(cfg[section][key]):
                raise ValueError(f"{FILE}: {section}.{key} must be {type(cfg[section][key]).__name__}")
            cfg[section][key] = value
    if cfg["gate"]["merge_method"] not in ("merge", "squash", "rebase"):
        raise ValueError(f"{FILE}: gate.merge_method must be merge, squash or rebase")
    return cfg


def use(text: str | None, source: str) -> dict:
    """Make TEXT (or the defaults, if None) the settings of this run."""
    global _current, _source, _text
    _current = parse(text) if text else copy.deepcopy(DEFAULTS)
    _source = source if text else "defaults (written for MessagePack-CSharp)"
    _text = text or ""
    return _current


def load_local(root: Path | None = None) -> dict:
    """Outside GitHub: ET_CONFIG, or .earned-trust.toml in ROOT, or the defaults."""
    path = Path(os.environ["ET_CONFIG"]) if os.environ.get("ET_CONFIG") else (root / FILE if root else None)
    if path and path.exists():
        return use(path.read_text(), str(path))
    return use(None, "")


def get() -> dict:
    return _current


def source() -> str:
    return _source


def digest() -> str:
    """Pinned in the receipt with the rules' code: the settings that let a change through."""
    return hashlib.sha256(_text.encode()).hexdigest()
