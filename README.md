# Sancho

A GitHub Action that reviews every pull request, writes a short evidence
brief, and keeps the PR blocked until a named person answers its findings and
signs for the change. The AI points at problems; a human decides and signs.

## Try it

Three ways, from no setup to the real Action:

1. **Look, nothing to install (1 minute).** Open [#8](../../pull/8): the brief at the top says
   what a person must read (42 of 1,392 lines), the findings sit on their lines in
   *Files changed*, and the merge stays blocked by the `sancho/human-accountability-gate`
   check until an owner signs. [#22](../../pull/22) shows critical code found through a helper.
2. **Run it on your machine (2 minutes, Python 3 only).**
   ```sh
   git clone https://github.com/adrianql5/sancho && cd sancho
   make test     # 65 tests
   make demo     # reviews the four challenge changes offline, plus the benchmark
   ```
   Then open `runs/ju26-issue-2297/brief.md` (the brief of #8), `runs/ju26-issue-2297/receipt.md`
   (a signed receipt) and `dashboard/index.html` (the benchmark).
3. **Open a pull request yourself and watch the real Action review it (3 minutes).** No setup:
   1. Open [`factory/sancho/commands.py` in edit mode](https://github.com/adrianql5/sancho/edit/main/factory/sancho/commands.py)
      (you need to be signed in to GitHub).
   2. Change anything, even one comment line, and click *Commit changes…* → *Propose changes* →
      *Create pull request*. GitHub makes the fork for you.
   3. Within a minute Sancho posts its brief on your pull request. This file is in a declared
      critical area, so you'll see the full flow: findings on their lines, the AI's citations
      checked by the judge, *Critical: signing and merging*, and *Only @adrianql5 can sign*.
   4. Reply `/explain <id>` to any finding, or try `/sign`: Sancho refuses, because only people
      with write access can sign. That refusal is the gate working.

## How it works inside

On every pull request the Action runs a pipeline of stages, each one written to a JSON file
the next one reads. Only one stage asks the LLM, and nothing it says is kept without proof:

1. **Classifier** sorts every changed file (generated, tests, docs, logic, public API) and groups
   generated files by pattern; the ones that don't match go to a person.
2. **Requirement tracer** ties each claim of the issue and the docs to code, tests and the test run.
3. **Scope auditor** flags changes the issue never asked for and claims that contradict checked facts.
4. **Prosecutor** collects accusations from fixed rules and from the LLM (Vultr Serverless Inference).
5. **Judge** keeps an accusation only if its file, lines and symbol are really in the diff. No AI.
6. **Sensitivity** finds critical code (declared areas, their helpers, patterns, AI) and its owners.
7. **Abstention gate** lists the decisions the AI won't take, for a person, with the evidence.
8. **Router** decides how much a person reads (T0, T1, T2) with rules written in the brief.
9. **Sampler** picks the spot-check files, seeded by the commit, so anyone can re-pick them.

Then the brief, the line comments, the check and, after `/sign`, the receipt. Every stage, its
module and its inputs: [factory/README.md](factory/README.md). The principles, trade-offs and
limits on one page: [docs/CONCEPT_CARD.md](docs/CONCEPT_CARD.md).

## See it work

| | |
|---|---|
| [#2](../../pull/2) [#4](../../pull/4) [#6](../../pull/6) [#8](../../pull/8) | The challenge's four AI-written changes to MessagePack-CSharp, against `ju26-base` |
| [#19](../../pull/19) | Critical code: a transfer fee in a declared `payments` area |
| [#22](../../pull/22) | Harder critical code: retries in a helper that `payments` calls, with no word about money in the diff |
| [Live numbers](https://adrianql5.github.io/sancho/) | Share of lines read by a person, findings accepted or refuted (rules vs. AI), time to signature and to merge |

To show a PR again from the start, run *Actions → reset demo PR*: it takes
several PR numbers (default: the six above). Earlier commands stop counting;
nothing is deleted.

## Set it up

1. Copy [`templates/sancho.yml`](templates/sancho.yml) to your
   repository's `.github/workflows/`.
2. Set up the merge gate once, as an owner of the repository:

   ```sh
   python3 factory/sancho.py protect --repo owner/name
   ```

   It adds a branch ruleset: the default branch takes changes only through
   PRs, merged once `sancho/human-accountability-gate` is green, with no
   bypass, admins included. `--branch B` protects another branch too;
   `--dry-run` prints the ruleset and changes nothing.

That's it. Every new PR gets a brief, its findings on their lines in
*Files changed*, and a blocked check until someone signs.

### Optional: add an LLM

Without an LLM it runs on fixed rules only, and says so in the brief. To add
one (any OpenAI-compatible endpoint), set these repository secrets:

| Secret | What it is |
|---|---|
| `LLM_BASE_URL` | The endpoint, e.g. `https://api.example.com/v1` |
| `LLM_API_KEY` | Its API key |
| `LLM_MODEL` | The model name |
| `LLM_EXTRA_BODY` | Optional. Extra JSON for each request. For models that think out loud: `{"chat_template_kwargs": {"enable_thinking": false}}` |

### Optional: settings for your repository

Put a `.sancho.toml` at the root of the default branch. It is read from
the PR's base branch, never from the PR, so a change can't loosen its own
rules. Without it, the defaults (written for MessagePack-CSharp) apply.

```toml
[gate]
merge_on_sign = true          # merge the PR as soon as it is signed

[review]
public_api = ['^src/MyLib/']  # a new `public` here forces a full read
tests = ['(^|/)tests?/']

[[critical]]                  # always read in full, signed by its owners
name = "payments"
paths = ['^src/payments/']
owners = ["ana", "luis"]      # GitHub logins; empty = CODEOWNERS
signatures = 2

[trust]
upstream_history = "auto"     # folder trust from MessagePack-CSharp's history:
                              # auto = only without a settings file; on / off
```

Every setting and its default: [`factory/sancho/config.py`](factory/sancho/config.py).
This repository's own: [`.sancho.toml`](.sancho.toml).

### Optional: workflow inputs

Add them under `with:` in the copied file.

| Input | Default | What it does |
|---|---|---|
| `issue_repo` | this repository | Where the issues your PRs implement live (`owner/name`) |
| `factory_repo` | `adrianql5/sancho` | Where to get the reviewer from (for a fork of it) |
| `factory_ref` | `main` | Which branch or tag of it to use |

## Use it

Answer the bot with commands, as a PR comment or as a reply on a finding's
line. The bot reacts 👍 when it reads a command, then replies below it.

| Command | Meaning |
|---|---|
| `/accept <id>` | This finding is real. It goes in the receipt as a known issue |
| `/accept all` | Accept every finding not answered yet |
| `/refute <id> "why"` | This finding is wrong, because… |
| `/explain <id>` | Tell me more about a finding, decision or claim |
| `/decide <ABS-id> <option> "why"` | My call on something the AI won't decide (public API, wire format, compatibility, security) |
| `/spotcheck clean "<a line from a sample file>"` | I opened the sample files and they look fine. The quoted line proves I opened one |
| `/spotcheck escape "what looks wrong"` | Something slipped through: read every file in full from now on |
| `/requirements ok "what I checked"` | The PR does what the issue asks (only asked when the issue has no written requirements) |
| `/requirements wrong "what is missing"` | It doesn't |
| `/reqs ...` | Short for `/requirements ...` |
| `/verify "answer"` | Optional answer to the question on changes that need a full read |
| `/sign "Full Name"` | I take responsibility for this change |
| `/sign` | The same, with the name on your GitHub profile |

In a reply on a finding's line you can leave out the id: `/accept`,
`/refute "why"` and `/explain` are about that finding.

The brief lists what is left to do. When it is all done, `/sign` turns the
check green and attaches a signed receipt. Only owners, members and
collaborators of the repository can sign; some changes need two signatures
(the owner of a critical area first, then anyone with write access). Answering
`request-changes`, `reject` or `wait-for-tests` blocks the signature until a
new commit or a different answer.
A PR that changes only documentation needs only a signature: no requirements
to confirm, no tests to run, no AI call.

**Critical code** (moving money, credentials, deleting data, reading
untrusted input) is always read in full, its owners decide whether it is
correct, and only they can sign it. It is found in five ways, and each can only
raise the level of review, never lower it:

| How | What it catches |
|---|---|
| Declared | Files in a `[[critical]]` area; owners from the area, or from `CODEOWNERS` |
| Reach | A file outside the area whose types the area's code uses (read from the base branch). Changing a helper changes its callers |
| Patterns | Changed lines, deleted ones too, about money (also money in floating point), credentials, cryptography, data deletion, untrusted input |
| AI | Lines the model calls sensitive, each citing file, line and symbol, checked by the judge |
| Situation | Critical and untested: the owner decides (on PRs to the default branch the tests run in your CI: the brief says to check it). In a folder whose trust was revoked: one more signature. Inside generated files: never hidden |

## Run it locally

Python 3 only, nothing to install.

| Command | What it does |
|---|---|
| `make demo` | Offline demo: reviews of the example changes, receipts, benchmark and dashboard |
| `make test` | The factory's own tests |
| `python3 factory/sancho.py review [--branch B] [--offline] [--no-llm]` | Review the cached branches (`--offline`: no git, no network) |
| `python3 factory/sancho.py cmd --branch B --as LOGIN "/accept LLM-1"` | Run a command on a review as LOGIN |
| `python3 factory/sancho.py status --branch B` | Show what is left on a review |
| `python3 factory/sancho.py test --branch B` | Run the tests a change adds (`dotnet`, or the .NET SDK image through Docker) |
| `python3 factory/sancho.py protect --repo R [--branch B] [--dry-run]` | Set up the merge gate on a repository (needs admin rights) |
| `python3 factory/sancho.py github --reset PR` | Start a PR's review again (earlier commands stop counting); in Actions: *reset demo PR* |

`python3 factory/sancho.py --help` lists the rest.

## Known gaps

Found in review and not fixed yet. Fine for a demo repository; worth fixing
before trusting it on a public one.

| Gap | What can happen |
|---|---|
| Only `/sign` checks write access | Anyone can `/decide`, `/accept`, `/refute`, `/requirements` or `/spotcheck`: answer for the owner, block a PR with `request-changes`, or undo the owner's answer. The receipt shows who did it |
| A stranger's `/spotcheck escape` counts | It lowers the trust of the folders involved for 90 days, on every PR |
| The trust ledger is any issue with its mark | The newest issue or PR containing `<!-- sancho-ledger -->` is taken as the ledger, whoever wrote it: an empty one erases the real escapes, a broken one makes every review fail. Only the 300 newest issues and PRs are searched |
| `merge_on_sign` ignores CI | A signed PR is merged even if its `ci` checks fail: the ruleset only requires the Sancho gate. Add your CI check to the ruleset, or merge by hand |
| *reset demo PR* stops at the first failure | With several numbers, the PRs after a failing one are not reset |
