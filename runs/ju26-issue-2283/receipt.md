# Accountability Receipt · #2283 Generator and analyzer crash with IndexOutOfRangeException on a closed generic struct from a referenced assembly

- Commit `9df83c38409c8bfad0517aebffe48211eda4a5b4` on `ju26-issue-2283` · tier **T1** · policy: factory rules (earned_trust/gate.py + classifier.py)
- Signed by: Demo Owner (@demo-owner, 2026-11-14T06:06:35Z)
- Receipt hash: `26b05a0427efd1068f60b4e5f7dedd464575db56b33bcf415d86c95508e87d2d`

## Checked

- Classification of 4 files (heuristic: diff shape + text within each shape + regex rules (Roslyn classifier not used)) — **machine**
- Pattern check over 0 snapshots: 0 outlier(s) routed to a human — **machine**
- Citations of 2 accusations (1 rejected) — **machine (judge)**
- 4 claims traced to diff lines and tests — **machine**
- Read 39 lines in 3 files (T1) — **human:demo-owner**

## Not checked

- The rest of the test suite — only the 3 tests this change adds were run (docker mcr.microsoft.com/dotnet/sdk:8.0, 2026-11-14T05:30:00Z)
- Semantic analysis with Roslyn — classification is diff heuristics + regex (Roslyn classifier is P2)
- LLM prosecution — NOT RUN: offline and no cached answer for this input — deterministic only for this run
- Claims REQ-2283-3 — no test in this change covers them
- Whether each finding's argument is right — the judge checks citations only; a human accepts or refutes

## Decisions the AI left to a human

- **ABS-1** (diagnostic-policy): `narrow-to-metadata-types` by @demo-owner — "Drop only diagnostics whose symbol comes from metadata; keep Location.None ones from this compilation"

## Findings

- P-GLOBAL-WRAP `src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs:239`: **accepted** by @demo-owner

## Residual risk accepted

- P-GLOBAL-WRAP accepted as a known issue: `reportDiagnostic` is wrapped by `ReportIfLocatedInCompilation` for every caller, so whatever `ReportIfLocatedInCompilation` filters out is dropped for all diag
- REQ-2283-3 UNVERIFIED: Diagnostics about types declared in the consuming compilation are still reported, even when their location is null

*The PR comment can be edited; this receipt's hash is also in the check run output and in ledger/receipts/.*
