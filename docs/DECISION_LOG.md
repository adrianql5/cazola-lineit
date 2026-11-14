# Decision log

Newest last. Each entry gives the decision, the alternative we turned down,
and why.

| Date | Decision | Turned down | Why |
|---|---|---|---|
| 2026-11-14 | Build a **reference implementation**, small and honest from end to end | A product with a UI of its own | The jury weighs the concept; GitHub already has a review UI |
| 2026-11-14 | **Do not use** the example findings from the concept draft (`[ThreadStatic]`, `reader.Depth--`, `0x92 → Ext 0x7f`, `PipeReader`/LZ4) | Reusing them as demo material | They are not in the real diffs: an LLM made them up. They are kept as a standing test of the judge (`factory/knowledge/draft_hallucinations.json`) |
| 2026-11-14 | Every finding, our deterministic ones included, goes through the judge | Trusting our own rules | One path for everything, and the judge is the place to measure from |
| 2026-11-14 | Classifier: diff shape + regex, **not Roslyn** (P2) | A Roslyn console tool | Time. The brief says so in *What was NOT checked* |
| 2026-11-14 | Requirements curated by a human per issue (`factory/requirements/`) | Claims extracted by an LLM | The requirement belongs to a person; the LLM can propose claims when one is configured |
| 2026-11-14 | Doc claims extracted from the diff automatically | Ignoring the README | A change's README is a claim about itself. #2234's README says MsgPack012 is checked, and no test does |
| 2026-11-14 | Facts table (`factory/knowledge/facts.json`) read by a human from the source | Asking the LLM about .NET APIs | `ExcludeFromCodeCoverageAttribute`: Microsoft's docs list netstandard2.0 and .NET Framework 4.0+. Our own prompt said "since 2.0", and the docs only go back to 4.0, so we wrote down what the docs say |
| 2026-11-14 | Statuses VERIFIED / PARTIAL / UNVERIFIED / CONTRADICTED; VERIFIED **only with a passing test run** | Counting "a test exists" as verified | A test nobody ran is not evidence that the claim holds |
| 2026-11-14 | Tiers by readable rules; **no confidence percentages** anywhere | A risk score | A score cannot be argued with; a rule can |
| 2026-11-14 | Sample `max(1, ceil(5%))` of hidden files, seeded by the commit SHA | A random sample from the server | Anyone can re-draw the same sample and audit it |
| 2026-11-14 | Trust ledger from upstream history (revert / fix follow-up in commit subjects, 730 days) | Waiting for production data | We have no production history; upstream git is real data. Its limits are in LESSONS |
| 2026-11-14 | Brief written by a template from stage JSON | An LLM-written summary | The brief cannot say anything no stage measured |
| 2026-11-14 | `/sign` requires every abstention decided and every finding accepted or refuted | Signing with open items | The receipt must not contain "unknown" next to a signature |
| 2026-11-14 | The receipt lives in the check run output and `ledger/receipts/` | Only the PR comment | Comments can be edited; check run outputs are fixed for each run |
| 2026-11-14 | **Bench-driven fix:** the classifier also compares the *text* inside each pattern | Shape only | The shape-preserving sweep (an attribute swapped in one snapshot) let **208 of 221** through with shape only, and **0 of 221** with the text check. No false outliers on the real branches |
| 2026-11-14 | **Bench-driven fix:** a shape shared by fewer files than the threshold is an outlier even when it is the biggest group | Biggest group = pattern | M10 (a lone new "snapshot" with code in it) was hidden and caught only because the sample of 1 was 1 of 1. Now it is FLAGGED |
| 2026-11-14 | "Flagged" in the bench means a finding, trigger or abstention cites a line **within 10 lines** of the defect | Anything in the same file | Same-file matching inflated 2 results; they are now ROUTED (in the must-read set), which is what they are |
| 2026-11-14 | Simulated sessions are labelled `simulated` and have no timing | Showing review minutes from demo sessions | They would be invented numbers. The dashboard shows minutes from live sessions only |
| 2026-11-14 | The worker runs only the tests the change adds (`--filter`), in the official .NET SDK image | The whole suite | Minutes instead of hours, and those are the tests the claims point at |
| 2026-11-14 | When the pinned SDK cannot build a test project (CS9057: the generator needs Roslyn 4.12, SDK 8.0.4xx has 4.11), retry with the .NET 9 SDK and record the deviation in `tests.json` | Calling it a failure of the change, or hiding the retry | It is an environment problem, and saying so is part of the evidence |
| 2026-11-14 | Never push to `hugoocoto/lineit` or to MessagePack upstream; the demo fork gets its pushes through a remote whose upstream push URL is disabled | | The owner's instruction |
| 2026-11-14 | **Python with only the standard library** | A framework for the pipeline | `make demo` must run anywhere with no install step, and the GitHub runner needs nothing but `python3` |
| 2026-11-14 | **Drop lineit; run the factory as a GitHub Action on every pull request** (`templates/earned-trust.yml` → reusable `.github/workflows/earned-trust.yml`) | The policy as a lineit canvas, run by a GitHub App on a Vultr VM | It is what a team would actually adopt: one file in `.github/workflows`, no server, and it runs by itself on every PR. The canvas was clearer to look at, but it added a language to learn and a binary to build |
| 2026-11-14 | **The PR's comments are the state**: every run replays the slash commands written since the last commit | A database or a state file in the repository | Nothing to host or keep in sync. GitHub records who wrote what and when, and a new commit starts a new gate by construction |
| 2026-11-14 | Who may sign = GitHub's `author_association` (OWNER, MEMBER, COLLABORATOR) | A list of logins in the factory | GitHub already knows who has write access to the repository |
| 2026-11-14 | Tests run in the same job on `pull_request`; comment runs reuse the result, kept hidden in the brief comment for the same commit SHA | Re-running `dotnet test` on every comment | A comment takes seconds instead of minutes, and the result is still tied to the commit it ran on |
| 2026-11-14 | If the pinned SDK fails with CS9057, the job retries on SDK 9 with `DOTNET_ROLL_FORWARD=Major`, and the brief records it as a deviation | Failing the evidence step | The same environment problem we hit locally, handled the same way and said out loud |
| 2026-11-14 | The receipt pins the hash of the routing rules (`gate.py` + `classifier.py`) | The hash of the policy canvas | The rules that decide the tier are still pinned to every signature |
| 2026-11-14 | LLM through repository secrets (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`); Vultr Serverless Inference works as is | A hosted service | Same OpenAI-compatible client as before; without secrets, the factory says `NOT RUN` and runs on its deterministic rules |
| 2026-11-14 | `/spotcheck clean` must quote a line only one sampled file has (a class or method name) | A bare "clean" | It shows the file was opened; quoting the new attribute does not count, since every file has it |
| 2026-11-14 | Findings also posted on their line in *Files changed*; commands work in those threads; every command gets an answer where it was written | Only the summary comment | That's where people review code, and an answer next to the question is easier to follow |
| 2026-11-14 | Trust learns from escapes: the hidden files' folders drop a level for 90 days; kept as JSON in a repository issue, with a comment per change | A file committed by the bot | Needs no write access to the code, and every change of trust is visible and can be discussed |
| 2026-11-14 | Issues without written requirements: the AI proposes them (if configured) and a person confirms with `/requirements ok`; without AI, the person says what they checked | Refusing to review | Works on any repository, and the receipt still says where the requirements came from |
| 2026-11-14 | `/explain <id>` answers from the stage data, no LLM | An LLM explanation | It cannot add anything the checks did not find |
| 2026-11-14 | The dashboard is published with GitHub Pages on every push to main | A file in the repo | One public link that is always current |
| 2026-11-14 | LLM: `qwen3.8-27b` on Vultr Serverless Inference, with thinking turned off (`LLM_EXTRA_BODY`) | `glm-5.3`, `glm-5.3-flash`, `deepseek-v4.1-flash-1017` | On the real prompt those three spent the whole answer budget (8,000 tokens) in a hidden reasoning field and returned no text; `qwen3.8-27b` answers in about 3 s with valid JSON |
| 2026-11-14 | The LLM is called once per commit; comment runs reuse its answers, kept hidden in the brief | Calling it on every comment | Same findings on every comment (so `/accept LLM-2` keeps meaning the same thing), and no extra cost |
| 2026-11-14 | AI findings are asked for in at most two short sentences, and cut in the brief with `/explain` for the rest | Showing the model's full text | The first real answers were paragraphs long |

