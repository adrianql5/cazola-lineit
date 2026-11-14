"""The worker: runs the tests a change adds, so a claim can be VERIFIED and
not only PARTIAL. In GitHub Actions it runs `dotnet` in the PR's checkout;
locally it uses a worktree of the MessagePack clone and `dotnet`, or the
official .NET SDK image through Docker. The result is tied to the commit SHA;
the tracer ignores results for another commit.

    python3 factory/et.py test --branch ju26-issue-2297 [--repo PATH]
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from . import pipeline, sources

IMAGE = "mcr.microsoft.com/dotnet/sdk:8.0"


def projects_and_filter(tests_added: list[dict]) -> tuple[list[str], str]:
    projs, names = set(), []
    for t in tests_added:
        parts = t["file"].split("/")
        projs.add(f"{parts[0]}/{parts[1]}/{parts[1]}.csproj")
        names.append(t["name"])
    return sorted(projs), "|".join(f"FullyQualifiedName~{n}" for n in sorted(set(names)))


def script(projs: list[str], filt: str) -> str:
    # one project after the other, each reported, so one that cannot build does not hide the others
    return "; ".join(f'echo "=== {p}"; dotnet test "{p}" -c Release --filter "{filt}" --nologo; echo "=== exit $?"'
                     for p in projs)


def parse(out: str) -> dict:
    passed = sum(int(x) for x in re.findall(r"Passed:\s+(\d+)", out))
    failed = sum(int(x) for x in re.findall(r"Failed:\s+(\d+)", out))
    per = []
    for proj, body in re.findall(r"=== (\S+\.csproj)\n(.*?)=== exit", out, re.S):
        m = re.search(r"=== exit (\d+)", out[out.index(proj):])
        pp = sum(int(x) for x in re.findall(r"Passed:\s+(\d+)", body))
        ff = sum(int(x) for x in re.findall(r"Failed:\s+(\d+)", body))
        st = "PASS" if m and m.group(1) == "0" and pp and not ff else ("FAIL" if ff else "ERROR")
        per.append({"project": proj, "status": st, "passed": pp, "failed": ff,
                    "errors": sorted(set(re.findall(r"error (CS\d+|NU\d+|MSB\d+)", body)))})
    if per and all(x["status"] == "PASS" for x in per):
        status = "PASS"
    elif failed:
        status = "FAIL"
    else:
        status = "ERROR"
    return {"status": status, "passed": passed, "failed": failed, "per_project": per}


def execute(workdir: Path, tests_added: list[dict], sha: str, *, image: str = IMAGE,
            ignore_global_json: bool = False, docker: bool = False) -> dict:
    projs, filt = projects_and_filter(tests_added)
    if not projs:
        return {"status": "NOT RUN", "sha": sha, "why": "the change adds no tests"}
    deviations, env = [], {}
    if ignore_global_json:
        (workdir / "global.json").unlink(missing_ok=True)
        deviations.append(f"global.json (SDK 8.0.402) removed to build with {image if docker else 'the installed SDK'}")
        deviations.append("DOTNET_ROLL_FORWARD=Major: the net8.0 test host runs on a newer runtime")
        env["DOTNET_ROLL_FORWARD"] = "Major"
    inner = script(projs, filt)
    if docker:
        if not shutil.which("docker"):
            return {"status": "NOT RUN", "sha": sha, "why": "docker is not available"}
        flags = [x for k, v in env.items() for x in ("-e", f"{k}={v}")]
        cmd = ["docker", "run", "--rm", *flags, "-v", f"{workdir}:/src", "-w", "/src", image, "bash", "-lc", inner]
        how = f"docker {image}"
    else:
        if not shutil.which("dotnet"):
            return {"status": "NOT RUN", "sha": sha, "why": "dotnet is not installed"}
        ver = subprocess.run(["dotnet", "--version"], capture_output=True, text=True, cwd=workdir).stdout.strip()
        cmd, how = ["bash", "-lc", inner], f"dotnet {ver}"
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=workdir, env={**os.environ, **env})
    out = p.stdout + p.stderr
    r = parse(out)
    why = (f"{r['passed']} passed, {r['failed']} failed ({how})" if r["status"] != "ERROR" else
           "; ".join(f"{x['project'].split('/')[1]}: {x['status']} {', '.join(x['errors'])}" for x in r["per_project"])
           or "build or run error, see log_tail")
    if "ThrowShallowClone" in out:
        why += " — the checkout is shallow and the build versions itself from git history (fetch-depth: 0 fixes it)"
    if deviations:
        why += f" — deviation: {'; '.join(deviations)}"
    return {**r, "sha": sha, "how": how, "command": inner, "projects": projs, "deviations": deviations,
            "seconds": round(time.time() - t0), "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "why": why, "log_tail": out[-4000:]}


def run(branch: str, repo: str | None = None, image: str = IMAGE, ignore_global_json: bool = False) -> dict:
    """Locally: a worktree of the MessagePack clone at the branch's commit."""
    repo = repo or os.environ.get("ET_REPO") or str(sources.DEFAULT_REPO)
    change = sources.load(branch, offline=True)
    run_dir = pipeline.RUNS / branch
    tracer = json.loads((run_dir / "tracer.json").read_text())
    work = Path(tempfile.mkdtemp(prefix=f"et-{branch}-"))
    subprocess.run(["git", "-C", repo, "worktree", "add", "--detach", str(work), change.sha], check=True, capture_output=True)
    try:
        result = execute(work, tracer["tests_added"], change.sha, image=image, ignore_global_json=ignore_global_json,
                         docker=not shutil.which("dotnet"))
    finally:
        subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", str(work)], capture_output=True)
    (run_dir / "tests.json").write_text(json.dumps(result, indent=1))
    return result
