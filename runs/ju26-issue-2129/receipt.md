# Accountability Receipt · #2129 Feature Request: Allow generation of Formatter for a type in a referenced assembly

- Commit `083afd994c1c9a994cb2cd5aa0b6ad805a621457` on `ju26-issue-2129` · tier **T2** · policy: factory rules (earned_trust/gate.py + classifier.py)
- Signed by: Demo Owner (@demo-owner, 2026-11-14T06:06:35Z)
- Receipt hash: `77907ba8d7498d465350189ccdb5af4bfd75c10959bf0d21fb6eb9956bdf8b8a`

## Checked

- Classification of 28 files (heuristic: diff shape + text within each shape + regex rules (Roslyn classifier not used)) — **machine**
- Pattern check over 0 snapshots: 0 outlier(s) routed to a human — **machine**
- Citations of 3 accusations (1 rejected) — **machine (judge)**
- 13 claims traced to diff lines and tests — **machine**
- Spot-check of 1 hidden files: clean — **human:demo-owner**
- Read 1035 lines in 26 files (T2) — **human:demo-owner**

## Not checked

- The rest of the test suite — only the 13 tests this change adds were run (docker mcr.microsoft.com/dotnet/sdk:9.0, 2026-11-14T05:33:06Z)
- The pinned build environment — global.json (SDK 8.0.402) removed in the worktree to build with mcr.microsoft.com/dotnet/sdk:9.0; DOTNET_ROLL_FORWARD=Major: the net8.0 test host runs on the image's newer runtime
- Tests excluded from another test project — excluded tests were not run there (see the T2-TEST-EXCLUSION trigger)
- Semantic analysis with Roslyn — classification is diff heuristics + regex (Roslyn classifier is P2)
- LLM prosecution — NOT RUN: offline and no cached answer for this input — deterministic only for this run
- Claims DOC-2129-3, DOC-2129-4, DOC-2129-8, DOC-2129-9, DOC-2129-10 — no test in this change covers them
- 1 of 2 hidden mechanical files — not sampled; covered by the pattern check only
- Whether each finding's argument is right — the judge checks citations only; a human accepts or refutes

## Decisions the AI left to a human

- **ABS-1** (public-api): `request-changes` by @demo-owner — "New public API needs a PublicAPI entry and maintainer review"
- **ABS-2** (serialization-contract): `require-explicit-surrogate` by @demo-owner — "A contractless default fixes a wire contract nobody chose"
- **ABS-3** (analyzer-severity): `keep-error` by @demo-owner — "Misdeclared formatters cannot work; failing the build is right"
- **ABS-4** (ambiguous-requirement): `ask-issue-author` by @demo-owner — "The issue left the design open"

## Findings

- P-TEST-EXCLUDED `tests/MessagePack.SourceGenerator.MapModeExecutionTests/MessagePack.SourceGenerator.MapModeExecutionTests.csproj:14`: **accepted** by @demo-owner
- P-DOUBLE-RUN `src/MessagePack.SourceGenerator/MessagePackGenerator.cs:72`: **accepted** by @demo-owner

## Residual risk accepted

- P-TEST-EXCLUDED accepted as a known issue: New execution tests are excluded from MapModeExecutionTests, so the new formatters are never run in map mode: an evidence gap, not a pass
- P-DOUBLE-RUN accepted as a known issue: `GeneratedFormatterCollector.Collect` runs twice per formatter (once for the model with diagnostics off, once for the diagnostics): double cost, and the two run
- DOC-2129-3 UNVERIFIED: Nothing needs to be added to `ProjectA`.
- DOC-2129-4 UNVERIFIED: The surrogate's `[Key]` and `[IgnoreMember]` attributes describe the wire contract, and its members are matched to membe
- DOC-2129-8 UNVERIFIED: Implement `IMessagePackFormatter<T>` for the type to be serialized:
- DOC-2129-9 UNVERIFIED: The source generator writes formatters for non-generic, non-abstract classes and structs that the formatter can access. 
- DOC-2129-10 UNVERIFIED: When `[GeneratedMessagePackFormatter(SurrogateType = typeof(...))]` is used, each keyed member of the surrogate must mat

*The PR comment can be edited; this receipt's hash is also in the check run output and in ledger/receipts/.*
