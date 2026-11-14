## Earned-Trust Evidence Brief · #2283 · `ju26-issue-2283` @ `9df83c3840`

> [!CAUTION]
> **T1** · 1 decision the AI refused to make

1. **What:** implementation for #2283 — 4 files (1 semantic, 1 test, 2 docs).
2. **Why:** issue [#2283](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2283): "Generator and analyzer crash with IndexOutOfRangeException on a closed generic struct from a referenced assembly".
3. **Also touches:** nothing outside the issue that the auditor could find.
4. **Risk:** T1 — 1 semantic file to read. You read **39 of 228** changed lines; 0 mechanical files summarized, 0 sampled.
5. **Decide:** Is it acceptable that every diagnostic without a source location in this compilation is now dropped, not only those from referenced assemblies? → `ABSTAINED`, the AI will not decide this (1 in total).

**To turn `earned-trust/human-accountability-gate` green:**
- [ ] `/decide ABS-1 <accept-global-filter|narrow-to-metadata-types> "<reason>"` — diagnostic-policy
- [ ] `/accept P-GLOBAL-WRAP` or `/refute P-GLOBAL-WRAP "<evidence>"`
- [ ] `/sign "<Full Name>"` by the owner

<details><summary><b>Claims ↔ Evidence</b> — ⚪ UNVERIFIED 1 · ✅ VERIFIED 3</summary>

Requirements: `requirements/2283.json` (team (human), from the issue text; online, an LLM can propose these and a human confirms them). Tests: **PASS** — 3 passed, 0 failed (docker mcr.microsoft.com/dotnet/sdk:8.0)

| Claim | Status | Implementation | Tests in this change | Why |
|---|---|---|---|---|
| **REQ-2283-1** The generator and the analyzer do not crash (IndexOutOfRangeException) when a [MessagePackObject] member's type is a closed generic value ty | ✅ VERIFIED | `…tor/CodeAnalysis/TypeCollector.cs:985` | `ClosedGenericStruct_FromMetadataReference`, `ClosedGenericRecordStruct_FromMetadataReference` +1 | implemented, covered by 3 test(s) that ran and passed |
| **REQ-2283-2** The consuming assembly gets a generated resolver | ✅ VERIFIED | `…tor/CodeAnalysis/TypeCollector.cs:239` | `ClosedGenericStruct_FromMetadataReference`, `ClosedGenericRecordStruct_FromMetadataReference` +1 | implemented, covered by 3 test(s) that ran and passed |
| **REQ-2283-3** Diagnostics about types declared in the consuming compilation are still reported, even when their location is null | ⚪ UNVERIFIED | — | — | no implementing line and no test found |
| **DOC-2283-1** Closed generic types defined in a referenced assembly (for example, `Item<int>` where `Item<T>` is defined in another project or NuGet packa | ✅ VERIFIED | `README.md:1641` | `ClosedGenericStruct_FromMetadataReference`, `ClosedGenericRecordStruct_FromMetadataReference` +1 | implemented, covered by 3 test(s) that ran and passed |

</details>

<details open><summary><b>Findings</b> — 1 with a citation the judge verified</summary>

**P-GLOBAL-WRAP** · high · rules (deterministic) · `src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs:239`

`reportDiagnostic` is wrapped by `ReportIfLocatedInCompilation` for every caller, so whatever `ReportIfLocatedInCompilation` filters out is dropped for all diagnostics, not only the ones the issue is about (e.g. a diagnostic of the compilation's own type whose location is null or Location.None)

```diff
  239 +        this.reportDiagnostic = reportAnalyzerDiagnostic is null ? null : diagnostic => ReportIfLocatedInCompilation(reportAnalyzerDiagnostic, diagnostic);
```

*The judge verifies the citation, not the argument: the reasoning is the AI's until you `/accept` it.*

</details>

<details open><summary><b>What the AI refused to decide</b> — 1</summary>

**ABS-1 · diagnostic-policy** — Is it acceptable that every diagnostic without a source location in this compilation is now dropped, not only those from referenced assemblies?

- Why not the AI: Which diagnostics users may lose is analyzer policy; the AI can point at the filter, not weigh the trade-off.
- Evidence missing: a test showing a diagnostic of the compilation's own type with a null location is still reported
- Who decides: the analyzer maintainers
- Where: `src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs:239`
- Options: `accept-global-filter` / `narrow-to-metadata-types`

</details>

<details><summary><b>Accusations the judge rejected</b> — 1</summary>

| Id | Source | Accusation | Why rejected |
|---|---|---|---|
| DRAFT-4 | replay: our LLM-written concept draft | PipeReader with LZ4 decompression does not advance the reader on a partial frame | cites no file or line, and `PipeReader` appears nowhere in the diff |

</details>

<details><summary><b>What was NOT checked</b></summary>

- The rest of the test suite — only the 3 tests this change adds were run (docker mcr.microsoft.com/dotnet/sdk:8.0, 2026-11-14T05:30:00Z)
- Semantic analysis with Roslyn — classification is diff heuristics + regex (Roslyn classifier is P2)
- LLM prosecution — NOT RUN: offline and no cached answer for this input — deterministic only for this run
- Claims REQ-2283-3 — no test in this change covers them
- Whether each finding's argument is right — the judge checks citations only; a human accepts or refutes

</details>

<details><summary><b>Spot-check sample</b> — 0 of 0 hidden files</summary>


</details>

<details><summary><b>Phantom tests</b> — 1 proposed, not run</summary>

For **P-GLOBAL-WRAP**:
```csharp
[Fact]
public async Task DiagnosticWithoutSourceLocationFromOwnCompilationIsStillReported()
{
    // A [MessagePackObject] declared in THIS compilation whose diagnostic has no syntax location
    // must still be reported after `ReportIfLocatedInCompilation` was introduced.
    // Arrange a type in the test source, trigger a diagnostic created with Location.None,
    // and assert it appears in the analyzer results.
}
```

</details>

<details><summary>Provenance</summary>

- Source of the diff: replay cache (factory/cache) · diff sha256 `5225b3964527bd08`
- Classifier: heuristic: diff shape + text within each shape + regex rules (Roslyn classifier not used)
- Prosecutor LLM: NOT RUN: offline and no cached answer for this input
- Routing policy: factory rules (earned_trust/gate.py + classifier.py) · rules sha256 `cf2ba253bd60f8e6`
- Trust ledger: git log origin/master -n 2000 --no-merges (te-industry-tech-office/junction26-messagepack-csharp, a mirror of MessagePack-CSharp), 730 days up to 2026-10-23

</details>

<sub>Earned-Trust PR Factory · AI reviews. Humans sign. Evidence decides.</sub>
