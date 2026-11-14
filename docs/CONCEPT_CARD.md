# Concept card: Earned-Trust PR Factory

**Recommendation in one sentence.** Let AI review AI-written code, but only
let it *point*: every finding must cite lines a deterministic judge has
checked. The AI must name the decisions it will not make. A named human
signs a receipt that says what was checked, what was not, and what risk they
accept. All of it runs as a GitHub Action on every pull request, and a check
blocks the merge until someone signs.

*AI reviews. Humans sign. Evidence decides.*

## The idea, as built

```
pull request ─▶ classify ─┬─▶ trace ─▶ audit ─┐
                          └─▶ prosecute ──────┴─▶ JUDGE ─▶ abstain ─▶ route ─▶ sample ─▶ brief (PR comment)
                 (no LLM)                     (LLM optional)  (code)   (rules)   (rules)  (SHA seed)
PR comments: /spotcheck /decide /accept /refute /sign ─▶ gate ─▶ check run green + receipt
```

`templates/earned-trust.yml` in a repository calls the reusable workflow
`.github/workflows/earned-trust.yml`. On `pull_request` it reviews the diff,
runs the tests the PR adds, posts the brief and opens the check
`earned-trust/human-accountability-gate` as *action required*. On each PR
comment it re-runs and replays every slash command written since the last
commit, so the PR's comments are the state. GitHub's `author_association`
decides who may sign. When the gate is met, the check turns green with the
receipt in its output, and the stage outputs are kept as an artifact.

Each finding is also posted on its line in *Files changed*, and every command
gets its answer where it was written. The AI prosecutor is `qwen3.8-27b` on
Vultr Serverless Inference, called once per commit through an
OpenAI-compatible client; comment runs reuse its saved answer.

## Seven principles

1. **Deterministic evidence first.** No finding that blocks a merge comes from
   the AI alone. Classification, the judge, sampling and routing are code. The
   LLM can propose accusations, and the judge can discard them.
2. **Cite or be silent.** Every accusation names a file, a line range and a
   symbol. If the judge cannot find all three in the diff, the accusation is
   logged as `hallucination_rejected` and the human never sees it.
3. **Abstain out loud.** Public API, the default wire format, compatibility,
   analyzer severity, security and open requirements: the AI says
   `ABSTAINED` and names the decision, why it is not the AI's, the evidence
   that is missing, and who decides. It gives no confidence percentages,
   ever.
4. **Read less only where trust was earned.** A module's trust comes from its
   upstream history (reverts and fix follow-ups). When a spot-check finds
   something the pattern check missed (`/spotcheck escape`), the folder loses a
   level of trust for 90 days and is read in full; this is recorded in an issue
   of the repository. Only mechanical files that fit a pattern are hidden, and
   a sample of them, seeded by the commit SHA, goes to a human, who must quote
   a line from one of them to show it was opened.
5. **Name what was not checked.** Tests that were not run show as `NOT RUN`,
   never as passing. Every brief and every receipt has a *What was NOT
   checked* section.
6. **Critical code has a named owner.** Money, credentials, data deletion, untrusted
   input, or an area the team declares: always a full read, the owner decides whether
   it is correct, and only the owner can sign. Detectors and the AI can raise this
   level, never lower it.
7. **A signature covers exactly what was reviewed.** A new commit starts a
   new gate. The receipt pins the commit SHA, the diff's hash and the hash of
   the routing rules (`gate.py` + `classifier.py`) that let the change through.

## What it does on the real branches

| Branch | Tier | Lines the human reads | Why |
|---|---|---|---|
| #2297 ExcludeFromCodeCoverage | T1 | **42 of 1,392** | 220 of 222 snapshots share one pattern; the 2 that don't trace to an out-of-scope whitespace change in `TransformUtilities.cs:58`; the `#if !NETSTANDARD2_0 && !NETFRAMEWORK` guard contradicts the issue and Microsoft's docs → ABSTAINED. Its tests pass and the requirement is still contradicted: the test checks the guard |
| #2283 analyzer crash | T1 | 39 of 228 | `ReportIfLocatedInCompilation` filters *every* diagnostic → ABSTAINED (diagnostic policy) |
| #2234 SuppressSourceGeneration | T1 | 36 of 266 | first-wins on duplicate keys in the shared path; README claims MsgPack012 is checked, no test does |
| #2129 formatter for external types | **T2** | 1,035 of 1,043 | new public API, contractless default, 4 new *Error* rules, tests excluded from map mode → 4 abstentions. The factory saves no time here, on purpose |

Measured numbers are on https://adrianql5.github.io/cazola-lineit/, and each
one names its source: the benchmark (seeded recall, judge rejections, the
shape-preserving sweep, precision) and live numbers read from this
repository's pull requests (share of lines read by a person, findings accepted
or refuted by rules and by the AI, time from brief to signature and to merge),
rebuilt after every review.

## Trade-offs

- **GitHub-native, not a service.** A workflow plus PR comments, with no
  server to run. The trade-off: each command takes a workflow run, about a
  minute, instead of an instant reply.
- **Precision over recall in prosecution.** Rule-based accusations are few
  and specific. With no LLM key, the factory finds less, but nothing it
  says is invented.
- **Reading less is earned per module, not per PR.** A PR from a careful
  author in a REVOKED module still gets read in full.
- **Template briefs, not prose.** The brief is assembled from stage outputs
  by a template. It is less fluent than an LLM summary, and it cannot say
  something no stage measured.
- **Requirements are curated by a human** (`factory/requirements/*.json`).
  This is slower than letting the model extract them, but the requirement
  belongs to a person.

## Limits: what would make us stop trusting our own output

- **The judge checks citations, not arguments.** A true quote can still be
  used to argue something wrong, and only `/accept` or `/refute` settles it.
- **The classifier is heuristic** (regex plus diff shape, no Roslyn). A
  defect that keeps both the shape *and* the words of a pattern gets past
  everything except the 5% sample.
- **The trust ledger reads commit subjects.** A revert not called "revert",
  or a fix not called "fix", is invisible to it.
- **The AI's arguments can be wrong even when its citations are right.** On
  #2297 `qwen3.8-27b` claimed the attribute sits on the wrong class; the cited
  lines show it does not. The judge keeps it, and a person refutes it.
- **Small numbers.** Four real branches, 14 seeded defects and nine labelled
  findings. The labels were made by the build engineer (an AI) and must be
  re-labelled by a person before anyone quotes them.
- **Simulated sessions are not users.** The example receipts that `make demo`
  writes come from scripted sessions and carry no timing. The live dashboard
  shows time to signature and acceptance rates only once real people answer
  and sign real PRs.
- **The rules are written for MessagePack.** The T2 triggers and the pattern of
  generated files name MessagePack's paths; another repository would need them
  adjusted before the factory reads less there.
- **If the pattern is the bug, the factory is blind.** 220 snapshots that are
  all wrong in the same way form a clean pattern. The templates (`.tt`) are
  always read by a human for this reason.
- **Whoever can edit the workflow can turn it off.** The gate is only as
  strong as branch protection and the review of `.github/workflows/`.
