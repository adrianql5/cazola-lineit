## Earned-Trust Evidence Brief · #2234 · `ju26-issue-2234` @ `9007cee116`

1. **What:** Implementation for #2234 The analyzer does not work if SuppressSourceGeneration = true — 4 files (1 semantic, 2 test, 1 docs).
2. **Why:** issue [#2234](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2234): "The analyzer does not work if SuppressSourceGeneration = true".
3. **Also touches:** nothing outside the issue that the auditor could find.
4. **Risk:** T1 — 1 semantic file to read. You read **36 of 266** changed lines; 0 mechanical files summarized, 0 sampled.
5. **Decide:** nothing: the AI found no decision outside its remit.

**To turn `earned-trust/human-accountability-gate` green:**
- [ ] `/accept P-FIRST-WINS` or `/refute P-FIRST-WINS "<evidence>"`
- [ ] `/accept P-SILENT-SKIP` or `/refute P-SILENT-SKIP "<evidence>"`
- [ ] `/sign "<Full Name>"` by the owner

<details><summary><b>Claims ↔ Evidence</b> — ⚪ UNVERIFIED 1 · ✅ VERIFIED 8</summary>

Requirements: `requirements/2234.json` (team (human), from the issue text). Tests: **PASS** — 10 passed, 0 failed (docker mcr.microsoft.com/dotnet/sdk:9.0) — deviation: global.json (SDK 8.0.402) removed in the worktree to build with mcr.microsoft.com/dotnet/sdk:9.0; DOTNET_ROLL_FORWARD=Major: the net8.0 test host runs on the image's newer runtime

| Claim | Status | Implementation | Tests in this change | Why |
|---|---|---|---|---|
| **REQ-2234-1** The analyzer reports diagnostics for types with [MessagePackObject(SuppressSourceGeneration = true)], as it did in 3.1.0 | ✅ VERIFIED | `…tor/CodeAnalysis/TypeCollector.cs:1008` | `NoFormatterIsGeneratedForSuppressedType`, `SuppressedTypeRoundTripsThroughDynamicResolver` +7 | implemented, covered by 9 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **REQ-2234-2** Types that do get a generated formatter keep their behaviour: the change is on the shared collection path, so they must be covered too | ✅ VERIFIED | `…tor/CodeAnalysis/TypeCollector.cs:1023` | `DuplicateKeysAreReportedWithoutAnalyzerFailureForGeneratedTypes` | implemented, covered by 1 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **DOC-2234-1** A `[MessagePackObject]` type can opt out of source generation with `[MessagePackObject(SuppressSourceGeneration = true)]`. | ✅ VERIFIED | `README.md:1622` | `MemberWithoutKeyIsReported`, `AllowPrivateRequiredIsReported` +6 | implemented, covered by 8 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **DOC-2234-2** Members have a `[Key]` or `[IgnoreMember]` attribute ([MsgPack004](doc/analyzers/MsgPack004.md)). | ✅ VERIFIED | `README.md:1626` | `MemberWithoutKeyIsReported` | implemented, covered by 1 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **DOC-2234-3** Keys are unique and all of the same kind ([MsgPack005](doc/analyzers/MsgPack005.md)). | ✅ VERIFIED | `README.md:1627` | `DuplicateIntKeysAreReportedWithoutAnalyzerFailure`, `DuplicateStringKeysAreReportedWithoutAnalyzerFailure` +2 | implemented, covered by 4 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **DOC-2234-4** Non-public members require `AllowPrivate` ([MsgPack015](doc/analyzers/MsgPack015.md)). | ✅ VERIFIED | `README.md:1628` | `AllowPrivateRequiredIsReported`, `SourceGenerationOnlyDiagnosticsAreNotReportedWhenSuppressed` | implemented, covered by 2 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **DOC-2234-5** Members have types that are themselves serializable ([MsgPack003](doc/analyzers/MsgPack003.md)). | ✅ VERIFIED | `README.md:1629` | `MemberTypeMustBeMessagePackObjectIsReported` | implemented, covered by 1 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **DOC-2234-6** Types are accessible to the resolver ([MsgPack012](doc/analyzers/MsgPack012.md)). | ⚪ UNVERIFIED | `README.md:1630` | — | documented, but no test in this change mentions `MsgPack012`, `InaccessibleDataType` |
| **DOC-2234-7** The analyzer does not report the partial-class requirement ([MsgPack011](doc/analyzers/MsgPack011.md)) or the AOT-only checks ([MsgPack016]( | ✅ VERIFIED | `README.md:1632` | `SourceGenerationOnlyDiagnosticsAreNotReportedWhenSuppressed` | implemented, covered by 1 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |

</details>

<details open><summary><b>Findings</b> — 2 with a citation the judge verified</summary>

**P-FIRST-WINS** · medium · rules (deterministic) · `src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs:1023` (also lines 1039, 1163, 1179)

With duplicate keys the first member wins and the later one is dropped from the serialization model silently; only the MsgPack005 error stops the build. This is the shared collection path, so it also changes types that do get a generated formatter

```diff
 1023 +                        if (!intMembers.ContainsKey(member.IntKey))
```

**P-SILENT-SKIP** · medium · rules (deterministic) · `src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs:1008` (also lines 1148)

After reporting, the member is skipped with `continue`, so it is missing from the model; if the diagnostic's severity is lowered by the user, the generated formatter silently leaves it out

```diff
 1008 +                            continue; // The key kind does not match the other members; the diagnostic is reported, so skip this member.
```

*The judge verifies the citation, not the argument: the reasoning is the AI's until you `/accept` it.*

</details>

<details><summary><b>What the AI refused to decide</b> — 0</summary>

Nothing in this change matched an abstention rule.
</details>

<details><summary><b>Accusations the judge rejected</b> — 1</summary>

| Id | Source | Accusation | Why rejected |
|---|---|---|---|
| DRAFT-1 | replay: our LLM-written concept draft | A [ThreadStatic] UTF-8 buffer is reused across calls and can leak data between threads | cites no file or line, and `[ThreadStatic]` appears nowhere in the diff |

</details>

<details><summary><b>What was NOT checked</b></summary>

- The rest of the test suite — only the 10 tests this change adds were run (docker mcr.microsoft.com/dotnet/sdk:9.0, 2026-11-14T05:32:48Z)
- The pinned build environment — global.json (SDK 8.0.402) removed in the worktree to build with mcr.microsoft.com/dotnet/sdk:9.0; DOTNET_ROLL_FORWARD=Major: the net8.0 test host runs on the image's newer runtime
- Semantic analysis with Roslyn — classification is diff heuristics + regex (Roslyn classifier is P2)
- LLM prosecution — NOT RUN: offline and no cached answer for this input — deterministic only for this run
- Claims DOC-2234-6 — no test in this change covers them
- Whether each finding's argument is right — the judge checks citations only; a human accepts or refutes

</details>

<details><summary><b>Spot-check sample</b> — 0 of 0 hidden files</summary>


</details>

<details><summary><b>Phantom tests</b> — 1 proposed, not run</summary>

For **P-FIRST-WINS**:
```csharp
[Fact]
public async Task DuplicateKeyMemberIsNotSilentlyDroppedWhenDiagnosticIsSuppressed()
{
    // With MsgPack005 suppressed via .editorconfig, a duplicate [Key(0)] must not produce
    // a formatter that silently omits the second member.
}
```

</details>

<details><summary>Provenance</summary>

- Source of the diff: replay cache (factory/cache) · diff sha256 `0f232d0b0493d33a`
- Classifier: heuristic: diff shape + text within each shape + regex rules (Roslyn classifier not used)
- Prosecutor LLM: NOT RUN: offline and no cached answer for this input
- Routing policy: factory rules (earned_trust/gate.py + classifier.py) · rules sha256 `cf2ba253bd60f8e6`
- Trust ledger: git log origin/master -n 2000 --no-merges (te-industry-tech-office/junction26-messagepack-csharp, a mirror of MessagePack-CSharp), 730 days up to 2026-10-23

</details>

<sub>Earned-Trust PR Factory · AI reviews. Humans sign. Evidence decides.</sub>
