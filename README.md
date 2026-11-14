# cazola-lineit · Earned-Trust PR Factory

**The AI reviews AI-written code, and a named human signs for every change.**
Junction 2026 · Tieto challenge *Earned Trust in AI Code*.

On every pull request a GitHub Action, with nobody pressing anything:

1. reads the diff and writes an **Evidence Brief**: five lines first, then
   the details folded below;
2. keeps a finding only if its file, line and symbol **really exist** in the
   diff (a deterministic *judge*, no AI);
3. **abstains out loud** on decisions that are not the AI's to make: public
   API, wire format, compatibility, security;
4. runs the tests the PR adds, and tells the reviewer exactly which lines
   they must read and which ones it summarized;
5. keeps the check `earned-trust/human-accountability-gate` blocked until an
   owner answers in PR comments (`/decide`, `/accept`, `/sign`), and then
   publishes a signed **Accountability Receipt**.

*AI reviews. Humans sign. Evidence decides.*

| | |
|---|---|
| The concept on one page | [docs/CONCEPT_CARD.md](docs/CONCEPT_CARD.md) |
| Decisions, lessons | [docs/DECISION_LOG.md](docs/DECISION_LOG.md) · [docs/LESSONS_AND_FAILURE_MODES.md](docs/LESSONS_AND_FAILURE_MODES.md) |
| How the code is organised | [factory/README.md](factory/README.md) |
| **See it work** | the [pull requests](../../pulls) of this repository: the four AI-written changes of the challenge, each reviewed by the Action |

## Try it in one minute (offline, Python 3 only)

```sh
make demo                              # 4 reviews, example receipts, benchmark, dashboard (~15 s)
open dashboard/index.html              # the measurements, each with its source
open runs/ju26-issue-2297/brief.md     # the brief of the 237-file change
```

## Put it on a repository

Copy [`templates/earned-trust.yml`](templates/earned-trust.yml) to the
repository's `.github/workflows/`. In *Settings → Branches*, require the
check `earned-trust/human-accountability-gate`. That's all: every new PR
gets its brief. To add an LLM (any OpenAI-compatible endpoint, for example
Vultr Serverless Inference), set the repository secrets `LLM_BASE_URL`,
`LLM_API_KEY` and `LLM_MODEL`. Without them the factory runs on its
deterministic rules and says so.

## The example pull requests

The [issues](../../issues) and [pull requests](../../pulls) of this repository
are copies of the challenge's: four upstream MessagePack-CSharp issues and the
four AI-written changes for them (branches `ju26-issue-*`, opened against
`ju26-base`, a snapshot of MessagePack-CSharp at the commit the changes start
from). The Action reviews each one on its own.
