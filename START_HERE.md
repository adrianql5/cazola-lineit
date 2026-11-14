# Start here: the whole project, explained simply

*(En español: [EMPIEZA_AQUI.md](EMPIEZA_AQUI.md))*

## The problem, in one story

An AI can now write code. Give it a bug report and, ten minutes later, you
get a fix with 237 changed files.

Someone still has to **check** that fix before it goes into the product.
That person has two bad choices:

1. **Read all 237 files.** It takes hours, and by file 150 nobody is really
   paying attention.
2. **Click "approve" without reading.** It's fast, and one day a bug, or
   something worse, gets in, and nobody knows who let it through.

The obvious idea, "let another AI review it", does not fix this by itself.
AIs make things up. While writing *this very project*, we asked an AI to
draft example problems in the four real code changes, and it **invented
all four**. It named files, functions and byte codes that do not exist.
They sounded completely convincing.

So the real question is: **how can a person trust an AI-written change
without reading every line, and without blindly trusting another AI?**

## Our answer, in one sentence

> **The AI reviews, but it can only *point at* real lines. A program checks
> every one of those pointers. The AI must say out loud which decisions it
> won't make. And a person signs a receipt saying what they checked and what
> they didn't.**

*AI reviews. Humans sign. Evidence decides.*

## How it works: a restaurant kitchen

Think of a code change as a dish leaving a restaurant kitchen.

| In the kitchen | In our project |
|---|---|
| A cook makes the dish | An AI writes the code change |
| A food inspector looks at it and writes notes | The **AI reviewer** looks for problems |
| Every note must say *"plate 3, top left, this hair"*: if the inspector can't point at it, the note is thrown away | The **judge** (plain code, no AI) checks that every complaint points at a line that really exists in the change. Made-up complaints are thrown away |
| Some calls are not the inspector's job ("should we change the recipe?"). The inspector writes *"not my call, ask the chef"* | The AI **abstains**: "this changes a public promise to users, a person must decide" |
| 200 identical bread rolls? The inspector checks the pattern and tastes a few at random | 220 files that all got the same 3-line change are checked as a pattern, and a random handful is shown to the person |
| The head chef signs the ticket: *"I checked X, I didn't check Y, I accept the risk"* | The person types `/sign "Name"` and gets a **receipt** |

## What it found in the real code (no AI-invented stuff)

We used it on 4 real changes written by an AI for the open-source library
MessagePack. The most impressive case:

**The 237-file change (#2297).**
- Instead of 1,392 lines, the person reads **42**.
- 220 of the 222 generated files all received the same 3 lines. **Two did
  not.** The tool flagged those two, and they led to a small change somewhere
  else that nobody had asked for: the AI had sneaked in an unrelated edit.
- The change says a feature "isn't available" on older .NET versions and
  turns it off there. Microsoft's own documentation says it *is* available.
  The tool doesn't decide who's right. It says **"ABSTAINED: a person must
  decide"** and shows both sides.
- The tests **pass**, and the requirement is still broken, because the test
  checks the wrong behaviour. Green tests are not the same as a correct change.

**The new-feature change (#2129)** touches a public API, so the tool says
"read everything" (1,035 of 1,043 lines). It does not try to save time when
the risk is high, and that is on purpose.

## It runs by itself, on every pull request

All of this is a **GitHub Action**. Nobody runs anything by hand:

1. An AI (or a person) opens a pull request.
2. A minute later, a comment appears on the PR with the **brief**, and a check
   called `earned-trust/human-accountability-gate` turns up as **blocked**.
   The project's settings say a blocked check means *no merge*.
3. The reviewer answers by writing comments on the PR, such as
   `/accept SCOPE-1` or `/sign "Your Name"`. Each comment re-runs the Action,
   which updates the brief and ticks the boxes.
4. When everything is answered and an owner has signed, the check turns
   **green** and the **receipt** is attached to it. Now the PR can be merged.

The Action knows who wrote each comment because GitHub tells it, so only
the repository's owners and collaborators can sign. If the PR gets a new
commit, the review starts again: a signature is for exactly the code that was
reviewed.

Putting it on a repository is one file
([`templates/earned-trust.yml`](templates/earned-trust.yml)), copied into
`.github/workflows/`.

## Try it yourself (2 minutes)

You need **Python 3**. There's nothing to install, and it works offline.

Open a terminal in this folder and run:

```sh
# 1. Run everything: 4 reviews, example signatures, measurements, dashboard (~15 s)
make demo

# 2. Look at the results
open dashboard/index.html            # the measurements page
open runs/ju26-issue-2297/brief.md   # the report a reviewer reads (best viewed on GitHub)
```

### Be the reviewer (the same commands you would write on the PR)

Start a fresh review of the 237-file change:

```sh
python3 factory/et.py review --offline --branch ju26-issue-2297
```

Try to sign straight away. **It refuses**, and tells you what is missing:

```sh
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/sign "Your Name"'
```

Do what it asks:

```sh
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/spotcheck clean'
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/decide ABS-1 remove-guard "Microsoft docs say it exists there"'
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/accept SCOPE-1'
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/accept DRIFT-1'
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/accept DRIFT-2'
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/accept DRIFT-3'
python3 factory/et.py cmd --branch ju26-issue-2297 --as adrianql5 '/sign "Your Name"'
```

Now open your receipt:

```sh
open runs/ju26-issue-2297/receipt.md
```

(`--as` is who you pretend to be. Locally, only the logins in
`factory/owners.json` may sign; try `--as somebody-else` and watch it
refuse. On GitHub, it is GitHub that tells the Action who you are.)

## What each command means

| Command | Plain meaning |
|---|---|
| `/spotcheck clean` | "I looked at the random sample and it's fine" (`escape` = "I found something wrong": then you must read everything) |
| `/decide ABS-1 <option> "<why>"` | "The AI wouldn't decide this; here is my decision and my reason" |
| `/accept SCOPE-1` | "Yes, this problem is real; I'm aware of it" |
| `/refute SCOPE-1 "<why>"` | "No, this complaint is wrong, and here's why" |
| `/sign "Full Name"` | "I take responsibility for this change." Only works when everything above is done |

## Words you'll see

- **Brief**: the short report the reviewer reads. It opens with 5 lines,
  and the details are folded below.
- **Receipt**: the signed record of what was checked, by whom (machine or
  person), what wasn't checked, and what risk was accepted.
- **T0 / T1 / T2**: how carefully a person must read. T0 = a summary plus a
  random sample, T1 = only the risky parts, T2 = everything.
- **Judge**: plain code, no AI. It throws away any complaint that points at
  lines that aren't there.
- **Abstain**: the AI saying "this decision is not mine to make".
- **VERIFIED / PARTIAL / UNVERIFIED / CONTRADICTED**: for each thing the
  change claims, these mean proven by a test that actually ran / a test
  exists but wasn't run / no evidence / evidence says it's false.
- **Seeded defect**: a bug we planted on purpose, to measure whether the tool
  catches it.

## Honest limits

- We had no AI key while building this, so every problem shown was found by
  plain rules, not by an AI. With a key, an AI adds more suspects, and the
  judge filters them the same way.
- The "is this complaint real?" labels (9 findings) were made by the AI that
  helped build the tool. A person should re-check them.
- The example signatures in `runs/` are scripted and marked "simulated". We
  don't show "minutes saved" until real people use it, because we won't
  invent that number.
- The judge checks that a complaint points at real lines. It can't check
  whether the complaint's *reasoning* is right. That is why a person still
  accepts or refutes each one.

## Where to go next

- The concept on one page: [`docs/CONCEPT_CARD.md`](docs/CONCEPT_CARD.md)
- How to give the demo and the pitch: [`demo/PITCH_AND_DEMO_GUIDE.md`](demo/PITCH_AND_DEMO_GUIDE.md)
- What we decided and why: [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md)
- What went wrong and what we learned: [`docs/LESSONS_AND_FAILURE_MODES.md`](docs/LESSONS_AND_FAILURE_MODES.md)
- How the code is organised: [`factory/README.md`](factory/README.md)
