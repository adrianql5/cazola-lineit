# Lessons and failure modes

## 1. Our own draft hallucinated its findings (the incident)

The concept draft (`earned-trust-pr-factory.md`) was written with an LLM
before anyone read the branches. Its example findings sounded specific and
plausible:

| Draft said | Branch | In the real diff? |
|---|---|---|
| a `[ThreadStatic]` UTF-8 buffer reused across calls | #2234 | no: #2234 only touches `TypeCollector.cs`, a README and tests |
| `finally { reader.Depth--; }` can underflow | #2297 | no: #2297 adds an attribute in T4 templates and 222 snapshots |
| `DateTimeOffset` boxed, written as `0x92` then `Ext 0x7f` | #2129 | no: #2129 is a source-generator feature |
| `PipeReader` with LZ4 does not advance on a partial frame | #2283 | no: #2283 filters analyzer diagnostics |

**What we learned.** Specific is not the same as true. The draft named
files, types and byte codes, and none of them were there. This is exactly
the failure the Deterministic Diff Judge exists for. All four are replayed
in every run as accusations (`factory/knowledge/draft_hallucinations.json`),
and the judge rejects all four: "`PipeReader` appears nowhere in the diff".

Our build prompt had smaller cases of the same thing:
- it said the out-of-scope change in #2297 alters "exactly 1" snapshot; the
  classifier found **2**, and both trace to the same whitespace change;
- it said `ExcludeFromCodeCoverageAttribute` exists "since .NET Framework
  2.0"; the docs we could check list 4.0 and later, so the fact table says
  4.0+;
- it gave "402" for the guard and attribute pairs; the diff has 413 `#if`
  lines and 423 attribute lines in total, templates and tests included.

None of these change a conclusion, but each one would have been a false
statement in a demo if we had not counted ourselves.

## 2. A stale classifier

The classifier's rules are regexes written against today's code. A rename
(`reportDiagnostic` → `report`) or a new published package would silently
change what counts as T2. **Mitigations:** the T2 rules are listed in one
place (`classifier.py: T2_RULES`), the bench re-runs them on every change,
and a `/spotcheck escape` disables summary mode for the PR and is counted.
**Still open:** nobody is alerted when a rule stops matching anything.

## 3. Complacency in the spot-check

If the sample is always clean, people stop looking and type `/spotcheck
clean` anyway. The bench measured the cost: with the shape check alone, a
defect that keeps the shape escaped **208 of 221** times, and only the 5%
sample stood in its way. **Mitigations:** the text-inside-pattern check
(0 of 221 now), and the sample is re-drawable from the SHA, so a lazy
"clean" can be audited afterwards. **Still open:** we cannot tell whether
someone actually opened the sampled files. A `/spotcheck` that must quote
one line of each sampled file would make that visible.

## 4. "More context = more confidence"

A long, detailed brief feels trustworthy. A brief with 18 doc claims (our
first version on #2129) was noisier, not safer. **Mitigations:** five story
lines on top and the rest folded away; doc claims only from lines that name
something a test could check (a diagnostic ID or a code identifier); fenced
code skipped. Volume is not evidence: the thing to look at is the status
column.

## 5. LLM hallucinations about .NET APIs

The judge checks that a citation exists in the diff. It cannot check a claim
about the outside world ("this API does not exist on netstandard2.0"). Both
the AI-written change (#2297's README, a test comment) and our own prompt
made claims like that, and both were wrong in the same direction.
**Mitigations:** `factory/knowledge/facts.json`. Each fact was read by a
human from its source and has a URL and a date, and the auditor flags added
lines that contradict one (DRIFT-2, DRIFT-3 on #2297). **Limit:** the table
only knows what someone has put in it.

## 6. The judge checks citations, not arguments

"`ReportIfLocatedInCompilation` filters every diagnostic" cites a real line.
Whether that filtering is wrong is a judgement call. Accepted findings are
labelled *citation verified* and need `/accept` or `/refute`. In the scripted
session for #2234 we refuted P-SILENT-SKIP: the behaviour is real, but
before the change the same input crashed the analyzer.

## 7. Environments lie too

`dotnet test` on #2234 and #2129 failed with `CS9057` under the SDK that
`global.json` pins (8.0.402). The generator references Roslyn 4.12 and that
SDK has 4.11. It looked like a failing change, and it was not. The worker
reports per project, writes down the error code, and when we retry with
another SDK, the deviation goes into `tests.json` and the brief.

## 8. Cost and latency

| Step | Measured |
|---|---|
| Whole offline pipeline, 4 branches | about 1 s (stdlib Python) |
| One GitHub Actions run per PR event | about a minute (checkout + `setup-dotnet` + tests on `pull_request`; seconds of review) |
| Benchmark (14 seeded + 442 sweep mutants + 45 judge cases) | about 14 s |
| `dotnet test` of the tests a change adds (SDK image cached) | 19–35 s per branch |
| LLM prosecution | not measured: no API key was available while building |

The LLM is the only paid, slow and non-deterministic step, and the pipeline
does not depend on it. If it fails, the brief says `NOT RUN` and the
deterministic findings still stand.

## 9. Trust ledger heuristics

It reads commit subjects. A revert called "undo X", or a fix called "adjust
Y", is invisible to it. The repository root is REVOKED because of one revert
("Revert to v2's insecure-by-default mode") that touched the README. That is
correct by the rule, and coarse. Modules are directories cut at three levels,
so a REVOKED `src/MessagePack` does not make
`src/MessagePack.SourceGenerator` REVOKED.
