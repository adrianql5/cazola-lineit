# Accountability Receipt · #2297 Add ExcludeFromCodeCoverage attribute to generated code.

- Commit `a0aa5ab2de7f5a669d97e37184a89034c1de82b6` on `ju26-issue-2297` · tier **T1** · policy: factory rules (earned_trust/gate.py + classifier.py)
- Signed by: Demo Owner (@demo-owner, 2026-11-14T06:06:35Z)
- Receipt hash: `13a0368bbd47aeb529fc5a55700ba65ac520d8d03d224f4932edb8f35ab8c432`

## Checked

- Classification of 237 files (heuristic: diff shape + text within each shape + regex rules (Roslyn classifier not used)) — **machine**
- Pattern check over 222 snapshots: 2 outlier(s) routed to a human — **machine**
- Citations of 6 accusations (1 rejected) — **machine (judge)**
- 3 claims traced to diff lines and tests — **machine**
- Spot-check of 12 hidden files: clean — **human:demo-owner**
- Read 42 lines in 10 files (T1) — **human:demo-owner**

## Not checked

- The rest of the test suite — only the 2 tests this change adds were run (docker mcr.microsoft.com/dotnet/sdk:8.0, 2026-11-14T05:29:10Z)
- Semantic analysis with Roslyn — classification is diff heuristics + regex (Roslyn classifier is P2)
- LLM prosecution — NOT RUN: offline and no cached answer for this input — deterministic only for this run
- 214 of 226 hidden mechanical files — not sampled; covered by the pattern check only
- Whether each finding's argument is right — the judge checks citations only; a human accepts or refutes

## Decisions the AI left to a human

- **ABS-1** (compatibility): `remove-guard` by @demo-owner — "Microsoft docs list ExcludeFromCodeCoverageAttribute for netstandard2.0 and .NET Framework 4.0+; the guard only drops the feature for those users"

## Findings

- SCOPE-1 `src/MessagePack.SourceGenerator/Transforms/TransformUtilities.cs:58`: **accepted** by @demo-owner
- DRIFT-1 `src/MessagePack.SourceGenerator/Transforms/CompositeResolverTemplate.tt:7`: **accepted** by @demo-owner
- DRIFT-2 `README.md:1640`: **accepted** by @demo-owner
- DRIFT-3 `tests/MessagePack.SourceGenerator.Tests/CodeCoverageExclusionTests.cs:18`: **accepted** by @demo-owner

## Residual risk accepted

- SCOPE-1 accepted as a known issue: Out-of-scope change: no requirement of the issue explains this hunk — it only changes whitespace (a formatting fix unrelated to the issue)
- DRIFT-1 accepted as a known issue: REQ-2297-1 is contradicted: the attribute is compiled out for consumers that target netstandard2.0 or .NET Framework, so not all generated code carries it
- DRIFT-2 accepted as a known issue: DOC-2297-2 is contradicted: contradicted by FACT-ECC-AVAILABILITY: System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverageAttribute exists in .NET Standard 2.0 
- DRIFT-3 accepted as a known issue: The change states something FACT-ECC-AVAILABILITY contradicts: System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverageAttribute exists in .NET Standard 2.0 and 
- REQ-2297-1 CONTRADICTED: All generated code is decorated with [ExcludeFromCodeCoverage]
- DOC-2297-2 CONTRADICTED: The attribute is only emitted for targets where it is available (not `netstandard2.0` or .NET Framework).

*The PR comment can be edited; this receipt's hash is also in the check run output and in ledger/receipts/.*
