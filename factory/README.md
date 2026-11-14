# factory: the code of Sancho

AI reviews AI-written code. A named human signs for every change. The
factory reviews the four AI-written branches of the Junction 2026 Tieto
challenge (`ju26-issue-2283`, `-2234`, `-2129`, `-2297` of
MessagePack-CSharp). Each branch gets a story-first **Evidence Brief**:
claims traced to evidence, findings with verified citations, the decisions
the AI refused to make, and what was not checked. A human then signs an
**Accountability Receipt**.

```sh
python3 factory/sancho.py review --offline          # 4 briefs → runs/<branch>/brief.md
python3 factory/sancho.py demo                      # + scripted receipts, bench, dashboard
python3 factory/sancho.py github --target DIR       # what the GitHub Action runs on each PR event
python3 factory/sancho.py live                      # live numbers from the repo's PRs (needs GITHUB_TOKEN)
python3 factory/sancho.py protect --repo owner/name  # the merge gate as a branch ruleset (admin, once)
```

Python 3.10+, standard library only. `--offline` uses the cached diffs and
issues in `cache/`, with no network, git or GitHub.

## Stages

Each stage writes `runs/<branch>/<stage>.json` and reads the stages before it.

| # | Stage | Module | LLM? |
|---|---|---|---|
| 1 | Classifier: mechanical / semantic / public-contract / test / docs; pattern groups and outliers; T2 triggers | `sancho/classifier.py` | no |
| 2 | Requirement Tracer: REQ (human-curated) and DOC (from the diff) claims → lines, tests, test run | `tracer.py` | no |
| 3 | Spec-drift & Scope Auditor: out-of-scope hunks, contradictions, checked facts | `auditor.py` | no (optional) |
| 4a | Adversarial Prosecutor: rules, our draft's hallucinations, and the LLM if configured | `prosecutor.py`, `llm.py` | optional |
| 4b | Deterministic Diff Judge: file + lines + symbol must be in the diff | `judge.py` | no |
| 4c | Sensitivity: critical areas (declared, detected, AI, situation) and their owners | `sensitivity.py` | optional |
| 5 | Abstention Gate | `gate.py` | no |
| 6 | Risk Router (T0 / T1 / T2, as rules) | `gate.py` | no |
| 7 | Spot-check sampler, seeded by the commit SHA | `gate.py` | no |
| – | Brief, slash commands, receipt | `brief.py`, `commands.py`, `receipt.py` | no |
| – | Worker: `dotnet test` of the tests a change adds | `worker.py` | no |
| – | GitHub Actions: PR diff in; brief comment, a comment on each finding's line, check run and receipt out; commands replayed from PR and line comments, each answered where it was written | `github.py` | no |
| – | Trust ledger: upstream history, lowered for 90 days by a spot-check escape (kept in a repository issue) | `ledger.py` | no |
| – | Live measurements from the repository's PRs for the dashboard | `live.py`, `dashboard.py` | no |
| – | The merge gate as a branch ruleset, created or updated in place | `protect.py` | no |
| – | Per-repository settings (`.sancho.toml`, read from the base branch); merge on signature | `config.py`, `github.py` | no |

## Folders

```
cache/          replayed diffs, commits and issues of the 4 branches; upstream history for the ledger
requirements/   per-issue requirements, curated by people
knowledge/      checked facts (with sources), diagnostic IDs, our draft's hallucinated findings
bench/          seeded defects (mutate.py), the benchmark (run.py), labels of rule findings (labels.json) and of AI findings (ai_labels.json)
tests/          unittest: diff parser, judge, classifier, sampler, spot-check, gate, learning, the GitHub Actions entry point, live measurements
```

## LLM

Any OpenAI-compatible endpoint works. On GitHub this repository uses
`qwen3.8-27b` on **Vultr Serverless Inference**, configured with repository
secrets: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` and `LLM_EXTRA_BODY`
(`{"chat_template_kwargs": {"enable_thinking": false}}`: without it, reasoning
models spend the whole answer budget thinking and return nothing).
`LLM_MAX_TOKENS` (3,000) and `LLM_TIMEOUT` (300 s) have defaults, and
`sancho.py models` (or the `llm-check` workflow) lists the models.

The model is called once per commit. Its answer is cached by model, prompt
version and input hash, and kept hidden in the brief, so comment runs reuse
it and the findings stay the same. If the call fails or the answer cannot be
read, the brief says why and the deterministic stages still run.

`make demo` runs offline, without the LLM: its findings come from the rules
and the auditor only.

## Slash commands

`/spotcheck clean "<line>"|escape "<what>"` · `/decide <ABS-id> <option> "<reason>"` ·
`/accept <id>` · `/refute <id> "<evidence>"` · `/requirements ok|wrong "<note>"` ·
`/explain <id>` · `/verify "<answer>"` (T2, optional) · `/sign "<Full Name>"` (owner only: OWNER, MEMBER or
COLLABORATOR on GitHub, `owners.json` offline). On GitHub they are PR
comments; offline you run them with `sancho.py cmd --branch B --as LOGIN '<command>'`.
