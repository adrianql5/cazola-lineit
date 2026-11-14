## Earned-Trust Evidence Brief · #2297 · `ju26-issue-2297` @ `a0aa5ab2de`

> [!CAUTION]
> **T1** · 1 decision the AI refused to make

1. **What:** implement issue #2297 : Add ExcludeFromCodeCoverage attribute to generated code — 237 files (9 semantic, 1 test, 1 docs, 226 mechanical).
2. **Why:** issue [#2297](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2297): "Add ExcludeFromCodeCoverage attribute to generated code".
3. **Also touches:** `TransformUtilities.cs:58`, a whitespace-only change no requirement asks for. It is what changes 2 of 222 snapshots.
4. **Risk:** T1 — 7 semantic files and 2 outliers to read. You read **42 of 1,392** changed lines; 226 mechanical files summarized, 12 sampled.
5. **Decide:** REQ-2297-1 asks for "All generated code is decorated with [ExcludeFromCodeCoverage]" but the change leaves some targets out. Intended? → `ABSTAINED`, the AI will not decide this (1 in total).

**To turn `earned-trust/human-accountability-gate` green:**
- [ ] `/spotcheck clean|escape` after looking at the 12 sampled files
- [ ] `/decide ABS-1 <keep-guard|remove-guard> "<reason>"` — compatibility
- [ ] `/accept SCOPE-1` or `/refute SCOPE-1 "<evidence>"`
- [ ] `/accept DRIFT-1` or `/refute DRIFT-1 "<evidence>"`
- [ ] `/accept DRIFT-2` or `/refute DRIFT-2 "<evidence>"`
- [ ] `/accept DRIFT-3` or `/refute DRIFT-3 "<evidence>"`
- [ ] `/sign "<Full Name>"` by the owner

<details><summary><b>Claims ↔ Evidence</b> — ❌ CONTRADICTED 2 · ✅ VERIFIED 1</summary>

Requirements: `requirements/2297.json` (team (human), from the issue text). Tests: **PASS** — 2 passed, 0 failed (docker mcr.microsoft.com/dotnet/sdk:8.0)

| Claim | Status | Implementation | Tests in this change | Why |
|---|---|---|---|---|
| **REQ-2297-1** All generated code is decorated with [ExcludeFromCodeCoverage] | ❌ CONTRADICTED | `…orms/CompositeResolverTemplate.tt:8`, `…erator/Transforms/EnumTemplate.tt:9` | `AllGeneratedTypesAreExcludedFromCodeCoverage`, `ExcludeAttributeIsGuardedForTargetsWhereItIsUnavailable` | the attribute is compiled out for consumers that target netstandard2.0 or .NET Framework, so not all generated code carr |
| **DOC-2297-1** All generated formatters and resolvers are decorated with `[ExcludeFromCodeCoverage]`, so generated code does not skew code coverage reports | ✅ VERIFIED | `README.md:1639` | `AllGeneratedTypesAreExcludedFromCodeCoverage`, `ExcludeAttributeIsGuardedForTargetsWhereItIsUnavailable` | implemented, covered by 2 test(s) that ran and passed |
| **DOC-2297-2** The attribute is only emitted for targets where it is available (not `netstandard2.0` or .NET Framework). | ❌ CONTRADICTED | `README.md:1640` | `ExcludeAttributeIsGuardedForTargetsWhereItIsUnavailable` | contradicted by FACT-ECC-AVAILABILITY: System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverageAttribute exists in .NET S |

</details>

<details open><summary><b>Findings</b> — 4 with a citation the judge verified</summary>

**SCOPE-1** · medium · auditor (deterministic) · `src/MessagePack.SourceGenerator/Transforms/TransformUtilities.cs:58`

Out-of-scope change: no requirement of the issue explains this hunk — it only changes whitespace (a formatting fix unrelated to the issue)

```diff
   58 +                writer(anyConstraints ? "{\r\n" : " {\r\n");
```

**DRIFT-1** · high · auditor (deterministic) · `src/MessagePack.SourceGenerator/Transforms/CompositeResolverTemplate.tt:7`

REQ-2297-1 is contradicted: the attribute is compiled out for consumers that target netstandard2.0 or .NET Framework, so not all generated code carries it

```diff
    7 +#if !NETSTANDARD2_0 && !NETFRAMEWORK
```

Also raised by: P-TFM-GUARD (rules (deterministic)).

**DRIFT-2** · high · auditor (deterministic) · `README.md:1640`

DOC-2297-2 is contradicted: contradicted by FACT-ECC-AVAILABILITY: System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverageAttribute exists in .NET Standard 2.0 and in .NET Framework 4.0 and later (the oldest version the current docs list), and it can be put on classes and structs.

```diff
 1640 +The attribute is only emitted for targets where it is available (not `netstandard2.0` or .NET Framework).
```

**DRIFT-3** · medium · auditor (deterministic) · `tests/MessagePack.SourceGenerator.Tests/CodeCoverageExclusionTests.cs:18`

The change states something FACT-ECC-AVAILABILITY contradicts: System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverageAttribute exists in .NET Standard 2.0 and in .NET Framework 4.0 and later (the oldest version the current docs list), and it can be put on classes and structs.

```diff
   18 +    // The attribute is not available on netstandard2.0 or .NET Framework, so it is only emitted where it exists.
```

*The judge verifies the citation, not the argument: the reasoning is the AI's until you `/accept` it.*

</details>

<details open><summary><b>What the AI refused to decide</b> — 1</summary>

**ABS-1 · compatibility** — REQ-2297-1 asks for "All generated code is decorated with [ExcludeFromCodeCoverage]" but the change leaves some targets out. Intended?

- Why not the AI: Which target frameworks get a feature is a compatibility promise; the AI can show the gap (and the API docs), not decide it.
- Evidence missing: the PR author's reason for the guard; a test compiled for netstandard2.0 / net472 consumers
- Who decides: the PR owner, with the maintainers for supported target frameworks
- Where: `src/MessagePack.SourceGenerator/Transforms/CompositeResolverTemplate.tt:7`
- Options: `keep-guard` / `remove-guard`

</details>

<details><summary><b>Pattern</b> — 222 snapshots, 2 that do not fit</summary>

- **G1** (dominant, 220 files): `+#endif · +#if!ID&&!ID · +[global::ID.ID.ID.ID]`
- **G2** (outlier, 1 file): `+#endif · +#if!ID&&!ID · +[global::ID.ID.ID.ID] · +internalsealedclassID:global::ID.ID.ID<global::ID<ID>> · +{ · -{internalsealedclassID:global::ID.ID.ID<global::ID<ID>>`
- **G3** (outlier, 1 file): `+ · +#endif · +#if!ID&&!ID · +[global::ID.ID.ID.ID]`
  - outlier `…alizedMemberAndIsGenericNamed`1.HasPrivateSerializedMemberAndIsGenericNamedFormatter.g.cs`: beyond the pattern it adds 2 and removes 1 line(s); whitespace only: **True**
  - outlier `…edMemberAndIsGenericOrdinal`1.HasPrivateSerializedMemberAndIsGenericOrdinalFormatter.g.cs`: beyond the pattern it adds 1 and removes 0 line(s); whitespace only: **True**
  - explained by `src/MessagePack.SourceGenerator/Transforms/TransformUtilities.cs:58`: the outlier's only change beyond the pattern is whitespace, and this out-of-scope hunk only changes whitespace in the generator's output
  - explained by `src/MessagePack.SourceGenerator/Transforms/TransformUtilities.cs:58`: the outlier's only change beyond the pattern is whitespace, and this out-of-scope hunk only changes whitespace in the generator's output

</details>

<details><summary><b>Accusations the judge rejected</b> — 1</summary>

| Id | Source | Accusation | Why rejected |
|---|---|---|---|
| DRAFT-2 | replay: our LLM-written concept draft | `finally { reader.Depth--; }` can underflow the reader depth when an exception is thrown | cites no file or line, and `reader.Depth--` appears nowhere in the diff |

</details>

<details><summary><b>What was NOT checked</b></summary>

- The rest of the test suite — only the 2 tests this change adds were run (docker mcr.microsoft.com/dotnet/sdk:8.0, 2026-11-14T05:29:10Z)
- Semantic analysis with Roslyn — classification is diff heuristics + regex (Roslyn classifier is P2)
- LLM prosecution — NOT RUN: offline and no cached answer for this input — deterministic only for this run
- 214 of 226 hidden mechanical files — not sampled; covered by the pattern check only
- Whether each finding's argument is right — the judge checks citations only; a human accepts or refutes

</details>

<details><summary><b>Spot-check sample</b> — 12 of 226 hidden files</summary>

Seed `a0aa5ab2de7f5a66` (commit SHA): `random.Random(int(commit_sha[:16], 16)).sample(sorted(hidden files), max(1, ceil(0.05 x N)))`. Anyone can re-draw it.

- `tests/MessagePack.SourceGenerator.Tests/Resources/CustomFormatterViaAttributeOnField(True)/Formatters.MessagePack.GeneratedMessagePackResolver.HasFieldWithCustomFormatterAttributeFormatter.g.cs`
- `tests/MessagePack.SourceGenerator.Tests/Resources/EnumFormatter_CollidingTypeNames/Formatters.MessagePack.GeneratedMessagePackResolver.NS1.MyEnumFormatter.g.cs`
- `tests/MessagePack.SourceGenerator.Tests/Resources/GenericType/Formatters.MessagePack.GeneratedMessagePackResolver.MyGenericTypeFormatter`1.g.cs`
- `tests/MessagePack.SourceGenerator.Tests/Resources/GenericsOfT1T2Formatter/Formatters.MessagePack.GeneratedMessagePackResolver.TempProject.MyGenericObjectFormatter`2.g.cs`
- `tests/MessagePack.SourceGenerator.Tests/Resources/GenericsOfT1T2Formatter/Formatters.MessagePack.GeneratedMessagePackResolver.TempProject.MyObjectFormatter.g.cs`
- `tests/MessagePack.SourceGenerator.Tests/Resources/GenericsOfT1T2Formatter/MessagePack.GeneratedMessagePackResolver.g.cs`
- `tests/MessagePack.SourceGenerator.Tests/Resources/GenericsUnionFormatter_Nested/Formatters.MessagePack.GeneratedMessagePackResolver.TempProject.MyGenericObjectFormatter`1.g.cs`
- `tests/MessagePack.SourceGenerator.Tests/Resources/NonDefaultDeserializingConstructor_Private/Formatters.A.AFormatter.g.cs`
- `tests/MessagePack.SourceGenerator.Tests/Resources/NullableFormatter/Formatters.MessagePack.GeneratedMessagePackResolver.TempProject.MyObjectFormatter.g.cs`
- `tests/MessagePack.SourceGenerator.Tests/Resources/RecordWithPrimaryConstructor/MessagePack.GeneratedMessagePackResolver.g.cs`
- `tests/MessagePack.SourceGenerator.Tests/Resources/RecordWithWithInitOnlyProps/Formatters.MessagePack.GeneratedMessagePackResolver.TempProject.MyMessagePackObjectFormatter.g.cs`
- `tests/MessagePack.SourceGenerator.Tests/Resources/UnionFormatter(NestingClass)/MessagePack.GeneratedMessagePackResolver.g.cs`

</details>

<details><summary>Provenance</summary>

- Source of the diff: replay cache (factory/cache) · diff sha256 `97c928b30efe3c2c`
- Classifier: heuristic: diff shape + text within each shape + regex rules (Roslyn classifier not used)
- Prosecutor LLM: NOT RUN: offline and no cached answer for this input
- Routing policy: factory rules (earned_trust/gate.py + classifier.py) · rules sha256 `cf2ba253bd60f8e6`
- Trust ledger: git log origin/master -n 2000 --no-merges (te-industry-tech-office/junction26-messagepack-csharp, a mirror of MessagePack-CSharp), 730 days up to 2026-10-23

</details>

<sub>Earned-Trust PR Factory · AI reviews. Humans sign. Evidence decides.</sub>
