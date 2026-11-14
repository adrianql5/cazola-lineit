# factory: the Earned-Trust PR Factory

AI reviews AI-written code. A named human signs for every change. The
factory reviews the four AI-written branches of the Junction 2026 Tieto
challenge (`ju26-issue-2283`, `-2234`, `-2129`, `-2297` of
MessagePack-CSharp). Each branch gets a story-first **Evidence Brief**:
claims traced to evidence, findings with verified citations, the decisions
the AI refused to make, and what was not checked. A human then signs an
**Accountability Receipt**.

```sh
python3 factory/et.py review --offline          # 4 briefs → runs/<branch>/brief.md
python3 factory/et.py demo                      # + scripted receipts, bench, dashboard
python3 factory/et.py github --target DIR       # what the GitHub Action runs on each PR event
```

Python 3.10+, standard library only. `--offline` uses the cached diffs and
issues in `cache/`, with no network, git or GitHub.

## Stages

Each stage writes `runs/<branch>/<stage>.json` and reads the stages before it.

| # | Stage | Module | LLM? |
|---|---|---|---|
| 1 | Classifier: mechanical / semantic / public-contract / test / docs; pattern groups and outliers; T2 triggers | `earned_trust/classifier.py` | no |
| 2 | Requirement Tracer: REQ (human-curated) and DOC (from the diff) claims → lines, tests, test run | `tracer.py` | no |
| 3 | Spec-drift & Scope Auditor: out-of-scope hunks, contradictions, checked facts | `auditor.py` | no (optional) |
| 4a | Adversarial Prosecutor: rules, our draft's hallucinations, and the LLM if configured | `prosecutor.py`, `llm.py` | optional |
| 4b | Deterministic Diff Judge: file + lines + symbol must be in the diff | `judge.py` | no |
| 5 | Abstention Gate | `gate.py` | no |
| 6 | Risk Router (T0 / T1 / T2, as rules) | `gate.py` | no |
| 7 | Spot-check sampler, seeded by the commit SHA | `gate.py` | no |
| – | Brief, slash commands, receipt | `brief.py`, `commands.py`, `receipt.py` | no |
| – | Worker: `dotnet test` of the tests a change adds | `worker.py` | no |
| – | GitHub Actions: PR diff in, brief comment + check run + receipt out, commands replayed from PR comments | `github.py` | no |
| – | Trust ledger from upstream history; SQLite schema | `ledger.py` | no |

## Folders

```
cache/          replayed diffs, commits and issues of the 4 branches; upstream history for the ledger
requirements/   per-issue requirements, curated by people
knowledge/      checked facts (with sources), diagnostic IDs, our draft's hallucinated findings
bench/          seeded defects (mutate.py), the benchmark (run.py), labels, report.json
tests/          unittest: diff parser, judge, classifier, sampler, gate, the GitHub Actions entry point
```

## LLM

Any OpenAI-compatible endpoint works: Vultr Serverless Inference, a vLLM
of your own, or a partner model. Set `LLM_BASE_URL`, `LLM_API_KEY` and
`LLM_MODEL` (as repository secrets for the Action); `et.py models` lists the models. Each call is cached by input
hash, with the model and prompt version, under `cache/<branch>/llm/`, so
it can be replayed offline. If the call fails, the brief says `NOT RUN` and
the pipeline continues with the deterministic stages only.

**The demo material was produced with no LLM key**, so every finding in
`runs/` comes from the deterministic rules and the auditor.

## Slash commands

`/spotcheck clean|escape` · `/decide <ABS-id> <option> "<reason>"` ·
`/accept <id>` · `/refute <id> "<evidence>"` · `/verify "<answer>"` (T2,
optional) · `/sign "<Full Name>"` (owner only: OWNER, MEMBER or
COLLABORATOR on GitHub, `owners.json` offline). On GitHub they are PR
comments; offline you run them with `et.py cmd --branch B --as LOGIN '<command>'`.
