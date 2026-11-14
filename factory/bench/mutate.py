"""Seeded defects: known-bad variants of the four real changes.

Each mutation edits a copy of a parsed diff (keeping line numbers right)
and says where its defect is. The bench then asks one question per
mutation: did the defect reach a human? Either FLAGGED (a verified finding,
an outlier, a T2 trigger or an abstention cites it), ROUTED (it sits in
what the human must read), or ESCAPED (it hides in the summary and was not
sampled).
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from sancho import gitdiff, sources
from sancho.gitdiff import FileDiff, Hunk, Line


@dataclass
class Mutant:
    id: str
    branch: str
    what: str
    file: str
    line: int | None
    expect: str  # "flag", "route" or "escape-unless-sampled"
    change: sources.Change = field(repr=False, default=None)


def _renumber(f: FileDiff) -> None:
    for h in f.hunks:
        n = h.new_start
        for l in h.lines:
            if l.kind == "-":
                l.new_no = None
            else:
                l.new_no = n
                n += 1


def insert_after(f: FileDiff, pred, text: str) -> int:
    """Adds TEXT as an added line after the first line PRED accepts; returns its number."""
    for h in f.hunks:
        for i, l in enumerate(h.lines):
            if l.kind != "-" and pred(l):
                h.lines.insert(i + 1, Line("+", text, None, None))
                _renumber(f)
                return h.lines[i + 1].new_no
    raise LookupError(f"no line to insert after in {f.path}")


def replace_text(f: FileDiff, pred, fn) -> int:
    for h in f.hunks:
        for l in h.lines:
            if l.kind == "+" and pred(l):
                l.text = fn(l.text)
                return l.new_no
    raise LookupError(f"no line to replace in {f.path}")


def delete_added(f: FileDiff, pred) -> int:
    for h in f.hunks:
        for i, l in enumerate(h.lines):
            if l.kind == "+" and pred(l):
                n = l.new_no
                del h.lines[i]
                _renumber(f)
                return n
    raise LookupError(f"no line to delete in {f.path}")


def delete_test(f: FileDiff, name: str) -> int:
    """Removes the added test method NAME (its [Fact] line through the line before the next [Fact])."""
    for h in f.hunks:
        lines = h.lines
        for i, l in enumerate(lines):
            if l.kind == "+" and re.search(rf"\b{name}\s*\(", l.text):
                a = i - 1 if i and "[Fact]" in lines[i - 1].text else i
                b = next((j for j in range(i + 1, len(lines)) if "[Fact]" in lines[j].text), len(lines))
                n = lines[i].new_no
                del lines[a:b]
                _renumber(f)
                return n
    raise LookupError(name)


def new_file(path: str, added: list[str]) -> FileDiff:
    h = Hunk(0, 0, 1, len(added), "", [Line("+", t, None, i + 1) for i, t in enumerate(added)])
    return FileDiff(path=path, old_path=None, status="added", hunks=[h])


def base(branch: str) -> sources.Change:
    return copy.deepcopy(sources.load(branch, offline=True))


def finish(m: Mutant, c: sources.Change) -> Mutant:
    c.diff_text = c.diff_text + f"\n# seeded mutation {m.id}\n"  # distinct diff hash; sampling seed stays the commit's
    c.source = f"seeded mutation {m.id} of {c.branch}"
    m.change = c
    return m


def by_suffix(c: sources.Change, suffix: str) -> FileDiff:
    return next(f for f in c.files if f.path.endswith(suffix))


def snapshots(c: sources.Change) -> list[FileDiff]:
    return sorted((f for f in c.files if "/Resources/" in f.path and f.path.endswith(".g.cs")), key=lambda f: f.path)


ATTR = "ExcludeFromCodeCoverage]"


def mutants() -> list[Mutant]:
    out = []

    def mk(id, branch, what, expect, edit):
        c = base(branch)
        file, line = edit(c)
        out.append(finish(Mutant(id, branch, what, file, line, expect), c))

    # --- #2297: the 237-file change -------------------------------------
    def logic_in_snapshot(c):
        f = snapshots(c)[17]
        return f.path, insert_after(f, lambda l: ATTR in l.text, "\t\tif (value == null) { return; }")
    mk("M01", "ju26-issue-2297", "a line of logic slipped into one 'mechanical' snapshot", "flag", logic_in_snapshot)

    def drop_attr(c):
        f = snapshots(c)[40]
        return f.path, delete_added(f, lambda l: ATTR in l.text)
    mk("M02", "ju26-issue-2297", "one snapshot keeps the #if/#endif but loses the attribute", "flag", drop_attr)

    def emit_in_snapshot(c):
        f = snapshots(c)[101]
        return f.path, insert_after(f, lambda l: ATTR in l.text, "\tprivate static readonly global::System.Reflection.Emit.DynamicMethod Probe = null;")
    mk("M03", "ju26-issue-2297", "Reflection.Emit added inside a snapshot", "flag", emit_in_snapshot)

    def hand_edit_t4(c):
        f = by_suffix(c, "Transforms/FormatterTemplate.cs")
        return f.path, insert_after(f, lambda l: l.kind == "+", '            this.Write("\\t\\tif (options.Security is null) { throw new global::System.InvalidOperationException(); }\\r\\n");')
    mk("M04", "ju26-issue-2297", "the T4 output (.cs) edited by hand: a line its .tt does not have", "flag", hand_edit_t4)

    def unsafe_src(c):
        f = by_suffix(c, "TransformUtilities.cs")
        return f.path, insert_after(f, lambda l: "anyConstraints ?" in l.text, "                unsafe { byte* p = stackalloc byte[16]; }")
    mk("M05", "ju26-issue-2297", "unsafe code added to the generator", "flag", unsafe_src)

    def logic_oos(c):
        f = by_suffix(c, "TransformUtilities.cs")
        return f.path, replace_text(f, lambda l: "anyConstraints ?" in l.text,
                                    lambda t: t.replace('writer(anyConstraints ? "{\\r\\n" : " {\\r\\n");', 'writer(anyConstraints ? "{\\r\\n" : " {\\r\\n"); if (kind == "struct") { kind = "class"; }'))
    mk("M06", "ju26-issue-2297", "the out-of-scope hunk now also changes logic (not just whitespace)", "flag", logic_oos)

    def exclude_tests(c):
        f = new_file("tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj",
                     ['  <ItemGroup>', '    <Compile Remove="CodeCoverageExclusionTests.cs" />', '  </ItemGroup>'])
        c.files.append(f)
        return f.path, 2
    mk("M07", "ju26-issue-2297", "the new test file is excluded from its project", "flag", exclude_tests)

    def public_api(c):
        f = new_file("src/MessagePack/CoverageOptions.cs",
                     ["namespace MessagePack;", "", "public static class CoverageOptions", "{", "    public static bool Enabled { get; set; } = true;", "}"])
        c.files.append(f)
        return f.path, 3
    mk("M08", "ju26-issue-2297", "a new public type in the MessagePack package", "flag", public_api)

    # --- #2283 -----------------------------------------------------------
    def invert(c):
        f = by_suffix(c, "TypeCollector.cs")
        return f.path, replace_text(f, lambda l: "diagnostic.Location.IsInSource &&" in l.text,
                                    lambda t: t.replace("if (diagnostic.Location.IsInSource", "if (!diagnostic.Location.IsInSource"))
    mk("M09", "ju26-issue-2283", "ReportIfLocatedInCompilation's condition inverted", "route", invert)

    def lone_snapshot(c):
        f = new_file("tests/MessagePack.SourceGenerator.Tests/Resources/ClosedGenericStruct_FromMetadataReference/TempProject.MyResolver.g.cs",
                     ["// <auto-generated />", "partial class MyResolver", "{", "\tpublic static object Instance => null;", "}"])
        c.files.append(f)
        return f.path, 4
    mk("M10", "ju26-issue-2283", "a lone 'snapshot' that is really new code (no pattern to compare against)", "route", lone_snapshot)

    # --- #2234 -----------------------------------------------------------
    def remove_continue(c):
        f = by_suffix(c, "TypeCollector.cs")
        return f.path, delete_added(f, lambda l: l.text.strip().startswith("continue;"))
    mk("M11", "ju26-issue-2234", "one of the two `continue` statements removed (mixed keys crash again)", "route", remove_continue)

    def no_guard(c):
        f = by_suffix(c, "TypeCollector.cs")
        return f.path, replace_text(f, lambda l: "if (!intMembers.ContainsKey(member.IntKey))" in l.text,
                                    lambda t: t.replace("if (!intMembers.ContainsKey(member.IntKey))", "if (true)"))
    mk("M12", "ju26-issue-2234", "the duplicate-key guard removed: a duplicate key throws inside the analyzer again", "route", no_guard)

    def drop_test(c):
        f = by_suffix(c, "SuppressSourceGenerationAnalyzerTests.cs")
        return f.path, delete_test(f, "MemberWithoutKeyIsReported")
    mk("M13", "ju26-issue-2234", "the only MsgPack004 test deleted, README still claims it", "flag", drop_test)

    # --- #2129 -----------------------------------------------------------
    def emit_2129(c):
        f = by_suffix(c, "GeneratedFormatterCollector.cs")
        return f.path, insert_after(f, lambda l: l.kind == "+" and "{" in l.text,
                                    "        var il = new System.Reflection.Emit.DynamicMethod(\"x\", null, null).GetILGenerator();")
    mk("M14", "ju26-issue-2129", "Reflection.Emit in the new collector", "flag", emit_2129)

    return out


def shape_preserving(content_check: bool) -> list[Mutant]:
    """The attribute swapped for another in one snapshot at a time: the shape
    is the same, only the words change. One mutant per dominant snapshot."""
    c0 = sources.load("ju26-issue-2297", offline=True)
    out = []
    for i, f0 in enumerate(snapshots(c0)):
        if f0.deleted or not any(ATTR in l.text for l in f0.added_lines()):
            continue
        c = copy.deepcopy(c0)
        f = next(x for x in c.files if x.path == f0.path)
        n = replace_text(f, lambda l: ATTR in l.text, lambda t: t.replace("ExcludeFromCodeCoverage", "SuppressMessage"))
        out.append(finish(Mutant(f"S{i:03}", c.branch, "attribute swapped, same shape", f.path, n, "escape-unless-sampled"), c))
    return out
