# Accountability Receipt · #2234 The analyzer does not work if SuppressSourceGeneration = true

- Commit `9007cee1163c4a274fd60c3cc20c21ae63622786` on `ju26-issue-2234` · tier **T1** · policy: factory rules (earned_trust/gate.py + classifier.py)
- Signed by: Demo Owner (@demo-owner, 2026-11-14T06:06:35Z)
- Receipt hash: `63ac18eb87c80f20e3a24714079d0cbd416797c6e45515c7cc04bb778b5ab650`

## Checked

- Classification of 4 files (heuristic: diff shape + text within each shape + regex rules (Roslyn classifier not used)) — **machine**
- Pattern check over 0 snapshots: 0 outlier(s) routed to a human — **machine**
- Citations of 3 accusations (1 rejected) — **machine (judge)**
- 9 claims traced to diff lines and tests — **machine**
- Read 36 lines in 2 files (T1) — **human:demo-owner**

## Not checked

- The rest of the test suite — only the 10 tests this change adds were run (docker mcr.microsoft.com/dotnet/sdk:9.0, 2026-11-14T05:32:48Z)
- The pinned build environment — global.json (SDK 8.0.402) removed in the worktree to build with mcr.microsoft.com/dotnet/sdk:9.0; DOTNET_ROLL_FORWARD=Major: the net8.0 test host runs on the image's newer runtime
- Semantic analysis with Roslyn — classification is diff heuristics + regex (Roslyn classifier is P2)
- LLM prosecution — NOT RUN: offline and no cached answer for this input — deterministic only for this run
- Claims DOC-2234-6 — no test in this change covers them
- Whether each finding's argument is right — the judge checks citations only; a human accepts or refutes

## Decisions the AI left to a human

- none

## Findings

- P-FIRST-WINS `src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs:1023`: **accepted** by @demo-owner
- P-SILENT-SKIP `src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs:1008`: **refuted** by @demo-owner — Before the change the same input crashed the analyzer (AD0001); skipping after reporting MsgPack005 is the intended behaviour

## Residual risk accepted

- P-FIRST-WINS accepted as a known issue: With duplicate keys the first member wins and the later one is dropped from the serialization model silently; only the MsgPack005 error stops the build. This is
- DOC-2234-6 UNVERIFIED: Types are accessible to the resolver ([MsgPack012](doc/analyzers/MsgPack012.md)).

*The PR comment can be edited; this receipt's hash is also in the check run output and in ledger/receipts/.*
