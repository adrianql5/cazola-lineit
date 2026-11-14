## Earned-Trust Evidence Brief · #2129 · `ju26-issue-2129` @ `083afd994c`

> [!CAUTION]
> **T2** · full human read required · 4 decisions the AI refused to make

1. **What:** Agentic implementation of #2129 Feature Request: Allow generation of Formatter for a type in a referenced assembly — 28 files (9 semantic, 2 public-contract, 9 test, 6 docs, 2 mechanical).
2. **Why:** issue [#2129](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2129): "Feature Request: Allow generation of Formatter for a type in a referenced assembly".
3. **Also touches:** `T2-ANALYZER-SEVERITY`, `T2-PUBLIC-API`, `T2-SERIALIZATION-CONTRACT`, `T2-TEST-EXCLUSION`.
4. **Risk:** T2 — T2-ANALYZER-SEVERITY: new or changed analyzer rule severity: it can break users' builds. You read **1,035 of 1,043** changed lines; 2 mechanical files summarized, 1 sampled.
5. **Decide:** Is `class GeneratedMessagePackFormatterAttribute` the public API the package wants to support forever? → `ABSTAINED`, the AI will not decide this (4 in total).

**To turn `earned-trust/human-accountability-gate` green:**
- [ ] `/spotcheck clean|escape` after looking at the 1 sampled files
- [ ] `/decide ABS-1 <approve-shape|request-changes> "<reason>"` — public-api
- [ ] `/decide ABS-2 <accept-contractless-default|require-explicit-surrogate> "<reason>"` — serialization-contract
- [ ] `/decide ABS-3 <keep-error|downgrade-to-warning> "<reason>"` — analyzer-severity
- [ ] `/decide ABS-4 <accept-surrogate-design|ask-issue-author> "<reason>"` — ambiguous-requirement
- [ ] `/accept P-TEST-EXCLUDED` or `/refute P-TEST-EXCLUDED "<evidence>"`
- [ ] `/accept P-DOUBLE-RUN` or `/refute P-DOUBLE-RUN "<evidence>"`
- [ ] `/sign "<Full Name>"` by the owner

<details><summary><b>Claims ↔ Evidence</b> — ⚪ UNVERIFIED 5 · ✅ VERIFIED 8</summary>

Requirements: `requirements/2129.json` (team (human), from the issue text). Tests: **PASS** — 13 passed, 0 failed (docker mcr.microsoft.com/dotnet/sdk:9.0) — deviation: global.json (SDK 8.0.402) removed in the worktree to build with mcr.microsoft.com/dotnet/sdk:9.0; DOTNET_ROLL_FORWARD=Major: the net8.0 test host runs on the image's newer runtime

| Claim | Status | Implementation | Tests in this change | Why |
|---|---|---|---|---|
| **REQ-2129-1** [GeneratedMessagePackFormatter] on a partial class implementing IMessagePackFormatter<T> makes the generator write that formatter in the con | ✅ VERIFIED | `…agePack.Annotations/Attributes.cs:166` | `ContractlessClassRoundTrips`, `ContractlessClassNullRoundTrips` +2 | implemented, covered by 4 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **REQ-2129-2** The assembly that defines T does not reference MessagePack | ✅ VERIFIED | `…rceGenerator.ExternalTypes.csproj:4` | `ContractlessClassRoundTrips`, `ContractlessClassUsesStringKeysForPublicReadWriteMembers` +5 | implemented, covered by 7 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **REQ-2129-3** How keys and settings (Key, Union...) are given for T: the issue lists three alternatives and picks none | ✅ VERIFIED | `…agePack.Annotations/Attributes.cs:149`, `…is/GeneratedFormatterCollector.cs:15` | `ContractlessClassRoundTrips`, `ContractlessClassUsesStringKeysForPublicReadWriteMembers` +6 | implemented, covered by 8 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **DOC-2129-1** You can still get a source-generated formatter for it by declaring a `partial` formatter class in your own project and marking it with `[Gen | ✅ VERIFIED | `README.md:1642` | `FormatterMustBePartial`, `FormatterMustImplementFormatterOfT` +4 | implemented, covered by 6 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **DOC-2129-2** The source generator writes the body of `MyObjectFormatter`, and the generated `GeneratedMessagePackResolver` registers it automatically. | ✅ VERIFIED | `README.md:1652` | `GeneratedFormattersAreRegisteredInGeneratedResolver` | implemented, covered by 1 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **DOC-2129-3** Nothing needs to be added to `ProjectA`. | ⚪ UNVERIFIED | `README.md:1653` | — | documented, but no test in this change mentions `ProjectA` |
| **DOC-2129-4** The surrogate's `[Key]` and `[IgnoreMember]` attributes describe the wire contract, and its members are matched to members of the formatted  | ⚪ UNVERIFIED | `README.md:1659` | — | documented, but no test in this change mentions `IgnoreMember` |
| **DOC-2129-5** Formatter diagnostics are reported as `MsgPack019` through `MsgPack022`, listed in the [analyzers](doc/analyzers/index.md). | ✅ VERIFIED | `README.md:1688` | `FormatterMustBePartial`, `SurrogateMemberMustMatchFormattedType` +1 | implemented, covered by 3 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **DOC-2129-6** A class marked with `[GeneratedMessagePackFormatter]` is the target of source generation. The generator writes the body of the formatter int | ✅ VERIFIED | `doc/analyzers/MsgPack019.md:3` | `FormatterMustBePartial`, `FormatterMustImplementFormatterOfT` +4 | implemented, covered by 6 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **DOC-2129-7** A class marked with `[GeneratedMessagePackFormatter]` identifies the data type to serialize by its `IMessagePackFormatter<T>` interface. The | ✅ VERIFIED | `doc/analyzers/MsgPack020.md:3` | `FormatterMustBePartial`, `FormatterMustImplementFormatterOfT` +4 | implemented, covered by 6 test(s) that ran and passed (environment deviation: global.json (SDK 8.0.402) removed in the w |
| **DOC-2129-8** Implement `IMessagePackFormatter<T>` for the type to be serialized: | ⚪ UNVERIFIED | `doc/analyzers/MsgPack020.md:16` | — | documented, but no test in this change mentions `IMessagePackFormatter<T>` |
| **DOC-2129-9** The source generator writes formatters for non-generic, non-abstract classes and structs that the formatter can access. The data type named  | ⚪ UNVERIFIED | `doc/analyzers/MsgPack021.md:3` | — | documented, but no test in this change mentions `IMessagePackFormatter<T>` |
| **DOC-2129-10** When `[GeneratedMessagePackFormatter(SurrogateType = typeof(...))]` is used, each keyed member of the surrogate must match a public, read-wr | ⚪ UNVERIFIED | `doc/analyzers/MsgPack022.md:3` | — | documented, but no test in this change mentions `GeneratedMessagePackFormatter(SurrogateType = typeof(...))` |

</details>

<details open><summary><b>Findings</b> — 2 with a citation the judge verified</summary>

**P-TEST-EXCLUDED** · high · rules (deterministic) · `tests/MessagePack.SourceGenerator.MapModeExecutionTests/MessagePack.SourceGenerator.MapModeExecutionTests.csproj:14`

New execution tests are excluded from MapModeExecutionTests, so the new formatters are never run in map mode: an evidence gap, not a pass

```diff
   14 +    <Compile Include="..\MessagePack.SourceGenerator.ExecutionTests\**\*.cs" Exclude="..\MessagePack.SourceGenerator.ExecutionTests\**\GeneratedMessagePackResolver.cs;..\MessagePack.SourceGenerator.ExecutionTests\**\GeneratedFormatterForExternalTypes*.cs" />
```

**P-DOUBLE-RUN** · low · rules (deterministic) · `src/MessagePack.SourceGenerator/MessagePackGenerator.cs:72` (also lines 125)

`GeneratedFormatterCollector.Collect` runs twice per formatter (once for the model with diagnostics off, once for the diagnostics): double cost, and the two runs can disagree if one changes

```diff
   72 +                    if (GeneratedFormatterCollector.Collect(s.Left.Right, options, referenceSymbols, reportDiagnostic: null, request.Formatter, request.Surrogate, ct) is FullModel generatedModel)
```

*The judge verifies the citation, not the argument: the reasoning is the AI's until you `/accept` it.*

</details>

<details open><summary><b>What the AI refused to decide</b> — 4</summary>

**ABS-1 · public-api** — Is `class GeneratedMessagePackFormatterAttribute` the public API the package wants to support forever?

- Why not the AI: Public API in a published package is a product commitment; tests can show it works, not that it is the right shape.
- Evidence missing: API review by a maintainer; a PublicAPI.Unshipped.txt entry (none in this diff)
- Who decides: the package maintainers (API owners of MessagePack.Annotations)
- Where: `src/MessagePack.Annotations/Attributes.cs:166`
- Options: `approve-shape` / `request-changes`

**ABS-2 · serialization-contract** — Should the default for these types be contractless (every public read-write member, keyed by its name)?

- Why not the AI: The default wire contract decides compatibility of every message ever written with it; that is a product decision.
- Evidence missing: the maintainers' position on contractless as a default; round-trip tests against data written by an older version
- Who decides: the package maintainers: the wire format is a promise to every user
- Where: `src/MessagePack.Annotations/Attributes.cs:149`
- Options: `accept-contractless-default` / `require-explicit-surrogate`

**ABS-3 · analyzer-severity** — Should the new diagnostics ship as Error (build-breaking) rather than Warning?

- Why not the AI: Severity is policy about users' builds, not a property of the code.
- Evidence missing: maintainers' severity policy for new rules
- Who decides: the analyzer maintainers: a new Error breaks users' builds on upgrade
- Where: `src/MessagePack.SourceGenerator/AnalyzerReleases.Unshipped.md:26`
- Options: `keep-error` / `downgrade-to-warning`

**ABS-4 · ambiguous-requirement** — The issue lists 3 ways to give keys for T and picks none; the change invents another (SurrogateType + contractless). Which one?

- Why not the AI: Choosing between designs the issue left open is the requirement owner's call.
- Evidence missing: the issue author's choice; maintainers' preference
- Who decides: the issue author and the maintainers
- Where: `requirements/2129.json`
- Options: `accept-surrogate-design` / `ask-issue-author`

</details>

<details><summary><b>Accusations the judge rejected</b> — 1</summary>

| Id | Source | Accusation | Why rejected |
|---|---|---|---|
| DRAFT-3 | replay: our LLM-written concept draft | DateTimeOffset is boxed and written as 0x92 followed by Ext 0x7f, changing the wire format | cites no file or line, and `0x7f` appears nowhere in the diff |

</details>

<details><summary><b>What was NOT checked</b></summary>

- The rest of the test suite — only the 13 tests this change adds were run (docker mcr.microsoft.com/dotnet/sdk:9.0, 2026-11-14T05:33:06Z)
- The pinned build environment — global.json (SDK 8.0.402) removed in the worktree to build with mcr.microsoft.com/dotnet/sdk:9.0; DOTNET_ROLL_FORWARD=Major: the net8.0 test host runs on the image's newer runtime
- Tests excluded from another test project — excluded tests were not run there (see the T2-TEST-EXCLUSION trigger)
- Semantic analysis with Roslyn — classification is diff heuristics + regex (Roslyn classifier is P2)
- LLM prosecution — NOT RUN: offline and no cached answer for this input — deterministic only for this run
- Claims DOC-2129-3, DOC-2129-4, DOC-2129-8, DOC-2129-9, DOC-2129-10 — no test in this change covers them
- 1 of 2 hidden mechanical files — not sampled; covered by the pattern check only
- Whether each finding's argument is right — the judge checks citations only; a human accepts or refutes

</details>

<details><summary><b>Spot-check sample</b> — 1 of 2 hidden files</summary>

Seed `083afd994c1c9a99` (commit SHA): `random.Random(int(commit_sha[:16], 16)).sample(sorted(hidden files), max(1, ceil(0.05 x N)))`. Anyone can re-draw it.

- `src/MessagePack.SourceGenerator/Transforms/FormatterTemplate.cs`

</details>

<details><summary>Provenance</summary>

- Source of the diff: replay cache (factory/cache) · diff sha256 `063e4d41a1ccf6e4`
- Classifier: heuristic: diff shape + text within each shape + regex rules (Roslyn classifier not used)
- Prosecutor LLM: NOT RUN: offline and no cached answer for this input
- Routing policy: factory rules (earned_trust/gate.py + classifier.py) · rules sha256 `cf2ba253bd60f8e6`
- Trust ledger: git log origin/master -n 2000 --no-merges (te-industry-tech-office/junction26-messagepack-csharp, a mirror of MessagePack-CSharp), 730 days up to 2026-10-23

</details>

<sub>Earned-Trust PR Factory · AI reviews. Humans sign. Evidence decides.</sub>
