"""Tests of the parts that must not be wrong: the diff parser, the judge,
the classifier's outlier, the sampler and the signing gate.

    python3 -m unittest discover -s factory/tests -t factory
"""

import tempfile
import unittest
import unittest.mock
from pathlib import Path

from sancho import classifier, commands, gate, gitdiff, judge, pipeline, sources

PATCH = """diff --git a/src/A.cs b/src/A.cs
index 1..2 100644
--- a/src/A.cs
+++ b/src/A.cs
@@ -10,3 +10,4 @@ class A
 int x = 1;
-int y = 2;
+int y = 3;
+int z = Compute(y);
 return x;
"""


class DiffTests(unittest.TestCase):
    def test_line_numbers(self):
        f = gitdiff.parse(PATCH)[0]
        self.assertEqual((f.added, f.deleted), (2, 1))
        self.assertEqual(f.new_line(12).text, "int z = Compute(y);")
        self.assertEqual(f.old_line(11).text, "int y = 2;")
        self.assertIsNone(f.new_line(99))


class JudgeTests(unittest.TestCase):
    files = gitdiff.parse(PATCH)

    def acc(self, **kw):
        return {"id": "X", "claim": "c", "file": "src/A.cs", "line_start": 12, "line_end": 12, "symbol": "Compute", **kw}

    def test_accepts_a_real_citation(self):
        self.assertEqual(judge.verdict(self.acc(), self.files)["verdict"], "ACCEPTED")

    def test_rejects_lines_not_in_the_diff(self):
        v = judge.verdict(self.acc(line_start=500, line_end=501), self.files)
        self.assertEqual((v["verdict"], v["kind"]), ("REJECTED", "hallucination_rejected"))

    def test_rejects_a_symbol_not_on_the_lines(self):
        self.assertEqual(judge.verdict(self.acc(symbol="ThreadStatic"), self.files)["verdict"], "REJECTED")

    def test_rejects_unchanged_context(self):
        self.assertEqual(judge.verdict(self.acc(line_start=10, line_end=10, symbol="x"), self.files)["verdict"], "REJECTED")

    def test_rejects_no_citation(self):
        self.assertEqual(judge.verdict(self.acc(file=None, line_start=None), self.files)["verdict"], "REJECTED")

    def test_rejects_unknown_file(self):
        self.assertEqual(judge.verdict(self.acc(file="src/B.cs"), self.files)["verdict"], "REJECTED")


class ClassifierTests(unittest.TestCase):
    def test_2297_outliers_are_the_two_generic_snapshots(self):
        r = classifier.run(sources.load("ju26-issue-2297"))
        self.assertEqual(r["snapshots"], 222)
        self.assertEqual(r["groups"][0]["size"], 220)
        outliers = sorted(o["path"].rsplit("/", 1)[1] for o in r["outliers"])
        self.assertEqual(len(outliers), 2)
        self.assertTrue(all("HasPrivateSerializedMemberAndIsGeneric" in o for o in outliers))
        self.assertTrue(all(o["residue"]["whitespace_only"] for o in r["outliers"]))

    def test_2129_raises_t2_for_public_api(self):
        rules = {t["rule"] for t in classifier.run(sources.load("ju26-issue-2129"))["triggers"]}
        self.assertIn("T2-PUBLIC-API", rules)
        self.assertIn("T2-TEST-EXCLUSION", rules)


class SamplerTests(unittest.TestCase):
    def test_reproducible_from_the_commit_sha(self):
        c = sources.load("ju26-issue-2297")
        hidden = [f"f{i}" for i in range(226)]
        a, b = gate.sample(c, hidden), gate.sample(c, list(reversed(hidden)))
        self.assertEqual(a["sample"], b["sample"])
        self.assertEqual(a["n"], 12)  # ceil(5% of 226)

    def test_at_least_one(self):
        self.assertEqual(gate.sample(sources.load("ju26-issue-2297"), ["only"])["n"], 1)


class SpotcheckTests(unittest.TestCase):
    def test_clean_needs_a_line_only_one_sample_file_has(self):
        with tempfile.TemporaryDirectory() as d, unittest.mock.patch.dict("os.environ", {"SANCHO_LEDGER_DIR": d}):
            d = Path(d)
            rep = pipeline.review(sources.load("ju26-issue-2297"), use_llm=False, run_dir=d)
            _, msg = commands.apply(rep, d, "demo-owner", "/spotcheck clean")
            self.assertIn("Copy one line", msg)
            _, msg = commands.apply(rep, d, "demo-owner", '/spotcheck clean "[global::System.Diagnostics.CodeAnalysis.ExcludeFromCodeCoverage]"')
            self.assertIn("doesn't show which sample file", msg)
            state, msg = commands.apply(rep, d, "demo-owner", '/spotcheck clean "class MyEnumFormatter"')
            self.assertEqual(state["spotcheck"]["result"], "clean", msg)


class LearningTests(unittest.TestCase):
    def test_an_escape_makes_the_next_review_read_the_folder(self):
        from sancho import ledger
        mod = "tests/MessagePack.SourceGenerator.Tests/Resources"
        with unittest.mock.patch.object(ledger, "EVENTS", [{"kind": "escape", "pr": 8, "modules": [mod], "until": "2999-01-01"}]):
            with tempfile.TemporaryDirectory() as d:
                r = pipeline.review(sources.load("ju26-issue-2297"), use_llm=False, run_dir=Path(d), write=False)
        self.assertGreater(r["router"]["read"]["lines_must_read"], 1000)


class AnyIssueTests(unittest.TestCase):
    def change(self):
        c = sources.load("ju26-issue-2283")
        return sources.make("pr-99", {"issue": 99, "sha": c.sha, "subject": "fix", "author": "x"},
                            {"title": "Crash on generic structs", "body": "It crashes.", "url": ""}, c.diff_text, "test")

    def test_no_requirements_and_no_ai_asks_the_human(self):
        with tempfile.TemporaryDirectory() as d, unittest.mock.patch.dict("os.environ", {"SANCHO_LEDGER_DIR": d}):
            rep = pipeline.review(self.change(), use_llm=False, run_dir=Path(d))
            self.assertEqual(rep["tracer"]["requirements_status"], "missing")
            self.assertEqual(rep["auditor"]["out_of_scope"], [])  # no requirements: nothing to be out of scope of
            todo = [t["what"] for t in commands.todo(rep, commands.load(Path(d)))]
            self.assertIn("Say what this PR must do", todo)
            state, _ = commands.apply(rep, Path(d), "demo-owner", '/requirements ok "compared with the issue"')
            self.assertNotIn("Say what this PR must do", [t["what"] for t in commands.todo(rep, state)])

    def test_reqs_is_short_for_requirements(self):
        with tempfile.TemporaryDirectory() as d, unittest.mock.patch.dict("os.environ", {"SANCHO_LEDGER_DIR": d}):
            rep = pipeline.review(self.change(), use_llm=False, run_dir=Path(d))
            state, msg = commands.apply(rep, Path(d), "demo-owner", '/reqs ok "compared with the issue"')
            self.assertEqual(msg, "Requirements confirmed.")
            self.assertEqual(state["requirements"]["verdict"], "ok")

    def test_the_ai_proposes_requirements_for_a_person_to_confirm(self):
        from sancho import llm
        answer = {"model": "fake-model", "prompt_version": "t", "input_sha256": "0", "cached": False, "content": '[{"text": "No crash", "quote": "It crashes.", '
                  '"code": ["GetPropertyIdentifierLocation"], "tests": ["FromMetadataReference"]}]'}
        with tempfile.TemporaryDirectory() as d, unittest.mock.patch.object(llm, "chat", lambda *a, **k: answer):
            rep = pipeline.review(self.change(), use_llm=True, offline=False, run_dir=Path(d), write=False)
        tr = rep["tracer"]
        self.assertEqual(tr["requirements_status"], "proposed")
        req = tr["claims"][0]
        self.assertEqual((req["id"], req["status"] in ("PARTIAL", "VERIFIED")), ("REQ-99-1", True))
        self.assertIn("not yet confirmed", req["kind"])


class GateTests(unittest.TestCase):
    def test_cannot_sign_before_deciding_and_non_owner_cannot_sign(self):
        with tempfile.TemporaryDirectory() as d, unittest.mock.patch.dict("os.environ", {"SANCHO_LEDGER_DIR": d}):
            d = Path(d)
            rep = pipeline.review(sources.load("ju26-issue-2283"), use_llm=False, run_dir=d)
            _, msg = commands.apply(rep, d, "demo-owner", '/sign "Demo Owner"')
            self.assertIn("can't sign yet", msg)
            self.assertIn("/decide ABS-1", msg)  # the reply says what to type
            commands.apply(rep, d, "demo-owner", '/decide ABS-1 narrow-to-metadata-types "test"')
            commands.apply(rep, d, "demo-owner", "/accept P-GLOBAL-WRAP")
            _, msg = commands.apply(rep, d, "someone-else", '/sign "Some One"')
            self.assertIn("only people with write access", msg)
            state, msg = commands.apply(rep, d, "demo-owner", '/sign "Demo Owner"')
            self.assertTrue(state["signed_complete"], msg)
            self.assertEqual(commands.gate(rep, state)["conclusion"], "success")
            self.assertTrue((d / "receipt.json").exists())

    def test_accept_all_answers_every_open_finding_and_keeps_refutes(self):
        with tempfile.TemporaryDirectory() as d, unittest.mock.patch.dict("os.environ", {"SANCHO_LEDGER_DIR": d}):
            d = Path(d)
            rep = pipeline.review(sources.load("ju26-issue-2297"), use_llm=False, run_dir=d)
            commands.apply(rep, d, "demo-owner", '/refute DRIFT-2 "the issue asks for it"')
            state, msg = commands.apply(rep, d, "demo-owner", "/accept all")
            self.assertEqual(msg, "SCOPE-1, DRIFT-1, DRIFT-3 accepted. They go in the receipt as known issues.")
            self.assertEqual({k: v["verdict"] for k, v in state["findings"].items()},
                             {"SCOPE-1": "accepted", "DRIFT-1": "accepted", "DRIFT-2": "refuted", "DRIFT-3": "accepted"})
            self.assertFalse(any(i["what"].startswith("Answer") for i in commands.todo(rep, state)))
            _, msg = commands.apply(rep, d, "demo-owner", "/accept all")
            self.assertEqual(msg, "Every finding on this PR is already answered.")


if __name__ == "__main__":
    unittest.main()


README_PATCH = """diff --git a/README.md b/README.md
index 1..2 100644
--- a/README.md
+++ b/README.md
@@ -1,2 +1,2 @@
 # Project
-Old words.
+Run `make demo` to try `/accept` on a PR.
"""


class DocsOnlyTests(unittest.TestCase):
    def change(self):
        return sources.make("pr-docs", {"issue": 0, "sha": "c" * 40, "subject": "README", "author": "x"},
                            {"title": "", "body": "", "url": ""}, README_PATCH, "test")

    def test_a_docs_only_pr_asks_only_for_a_signature(self):
        with tempfile.TemporaryDirectory() as d, unittest.mock.patch.dict("os.environ", {"SANCHO_LEDGER_DIR": d}):
            rep = pipeline.review(self.change(), use_llm=False, run_dir=Path(d))
            tr = rep["tracer"]
            self.assertEqual((tr["requirements_status"], tr["execution"]["status"], tr["claims"]),
                             ("not needed", "NOT NEEDED", []))
            self.assertEqual([t["what"] for t in commands.todo(rep, commands.load(Path(d)))], ["Signature from an owner"])
            self.assertNotIn("Tests", [x["item"] for x in rep["not_checked"]])
            _, msg = commands.apply(rep, Path(d), "demo-owner", '/requirements ok "x"')
            self.assertIn("documentation only", msg)

    def test_the_ai_is_not_asked_about_a_diff_with_no_code(self):
        from sancho import llm, prosecutor
        c = self.change()
        with unittest.mock.patch.object(llm, "chat", side_effect=AssertionError("asked the AI")):
            accs, meta = prosecutor.ask_llm(c, classifier.run(c), offline=False)
        self.assertEqual((accs, meta["status"]), ([], "SKIPPED"))
