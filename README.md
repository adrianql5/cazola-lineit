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
5. puts each finding on its line in *Files changed*, and answers every
   command where it was written;
6. keeps the check `earned-trust/human-accountability-gate` blocked until an
   owner answers (`/decide`, `/accept`, `/sign`), and then publishes a signed
   **Accountability Receipt**;
7. learns: when a spot-check finds something the pattern check missed, that
   folder is read in full for 90 days (kept in the *Earned-Trust trust ledger* issue).

*AI reviews. Humans sign. Evidence decides.*

| | |
|---|---|
| The concept on one page | [docs/CONCEPT_CARD.md](docs/CONCEPT_CARD.md) |
| How the code is organised | [factory/README.md](factory/README.md) |
| The measurements, live | **https://adrianql5.github.io/cazola-lineit/**: the benchmark, and live numbers from this repository's PRs (share read by a person, findings accepted or refuted by rules and AI, time to signature and to merge), rebuilt after every review and every hour |
| **See it work** | the [pull requests](../../pulls) of this repository: the four AI-written changes of the challenge, each reviewed by the Action |

## Try it in one minute (offline, Python 3 only)

```sh
make demo                              # 4 reviews, example receipts, benchmark, dashboard (~15 s)
open dashboard/index.html              # the measurements, each with its source
open runs/ju26-issue-2297/brief.md     # the brief of the 237-file change
```

## Commands, as PR comments or replies on a finding's line

| Command | Means |
|---|---|
| `/spotcheck clean "<a line from one sample file>"` | I opened the random sample; it's fine. The quote proves the file was opened |
| `/spotcheck escape "<what looks wrong>"` | Something slipped through: read every file, and trust that folder less |
| `/decide ABS-1 <option> "<why>"` | My decision on something the AI won't decide |
| `/accept <id>` · `/refute <id> "<why>"` | This finding is real · it isn't, because… |
| `/requirements ok "<what I checked>"` | Only when the issue has no written requirements |
| `/explain <id>` | Tell me more about a finding, decision or claim |
| `/sign "<Full Name>"` | I take responsibility for this change (write access needed) |

To review the same PR again (for repeated demos), run *Actions → reset demo PR*: a
marker comment makes earlier commands stop counting, and the findings stay the same.

## Put it on a repository

Copy [`templates/earned-trust.yml`](templates/earned-trust.yml) to the
repository's `.github/workflows/`. In *Settings → Branches*, require the
check `earned-trust/human-accountability-gate`. That's all: every new PR
gets its brief. To add an LLM (any OpenAI-compatible endpoint, for example
Vultr Serverless Inference), set the repository secrets `LLM_BASE_URL`,
`LLM_API_KEY` and `LLM_MODEL` (and, for models that think out loud,
`LLM_EXTRA_BODY` = `{"chat_template_kwargs": {"enable_thinking": false}}`).
Without them the factory runs on its deterministic rules and says so.

## The example pull requests

The [issues](../../issues) and [pull requests](../../pulls) of this repository
are copies of the challenge's: four upstream MessagePack-CSharp issues and the
four AI-written changes for them (branches `ju26-issue-*`, opened against
`ju26-base`, a snapshot of MessagePack-CSharp at the commit the changes start
from). The Action reviews each one on its own.
