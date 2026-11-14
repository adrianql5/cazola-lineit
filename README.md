# cazola-lineit

A GitHub Action that reviews every pull request, writes a short evidence
brief, and keeps the PR blocked until a named person answers its findings and
signs for the change. The AI points at problems; a human decides and signs.

## See it work

| | |
|---|---|
| [#2](../../pull/2) [#4](../../pull/4) [#6](../../pull/6) [#8](../../pull/8) | The challenge's four AI-written changes to MessagePack-CSharp, against `ju26-base` |
| [#19](../../pull/19) | Critical code: a transfer fee in a declared `payments` area |
| [#22](../../pull/22) | Harder critical code: retries in a helper that `payments` calls, with no word about money in the diff |
| [Live numbers](https://adrianql5.github.io/cazola-lineit/) | Share of lines read by a person, findings accepted or refuted (rules vs. AI), time to signature and to merge |

To show a PR again from the start, run *Actions → reset demo PR*: it takes
several PR numbers (default: the six above). Earlier commands stop counting;
nothing is deleted.

## Set it up

1. Copy [`templates/earned-trust.yml`](templates/earned-trust.yml) to your
   repository's `.github/workflows/`.
2. Set up the merge gate once, as an owner of the repository:

   ```sh
   python3 factory/et.py protect --repo owner/name
   ```

   It adds a branch ruleset: the default branch takes changes only through
   PRs, merged once `earned-trust/human-accountability-gate` is green, with no
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

Put a `.earned-trust.toml` at the root of the default branch. It is read from
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
```

Every setting and its default: [`factory/earned_trust/config.py`](factory/earned_trust/config.py).
This repository's own: [`.earned-trust.toml`](.earned-trust.toml).

### Optional: workflow inputs

Add them under `with:` in the copied file.

| Input | Default | What it does |
|---|---|---|
| `issue_repo` | this repository | Where the issues your PRs implement live (`owner/name`) |
| `factory_repo` | `adrianql5/cazola-lineit` | Where to get the reviewer from (for a fork of it) |
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
collaborators of the repository can sign; some changes need two signatures.
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
| Situation | Critical and untested: the owner decides. In a folder whose trust was revoked: one more signature. Inside generated files: never hidden |

## Run it locally

Python 3 only, nothing to install.

| Command | What it does |
|---|---|
| `make demo` | Offline demo: reviews of the example changes, receipts, benchmark and dashboard |
| `make test` | The factory's own tests |
| `python3 factory/et.py review [--branch B] [--offline] [--no-llm]` | Review the cached branches (`--offline`: no git, no network) |
| `python3 factory/et.py cmd --branch B --as LOGIN "/accept LLM-1"` | Run a command on a review as LOGIN |
| `python3 factory/et.py status --branch B` | Show what is left on a review |
| `python3 factory/et.py test --branch B` | Run the tests a change adds (`dotnet`, or the .NET SDK image through Docker) |
| `python3 factory/et.py protect --repo R [--branch B] [--dry-run]` | Set up the merge gate on a repository (needs admin rights) |
| `python3 factory/et.py github --reset PR` | Start a PR's review again (earlier commands stop counting); in Actions: *reset demo PR* |

`python3 factory/et.py --help` lists the rest.
