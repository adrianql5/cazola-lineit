"""Tests of the parts that must not be wrong: the diff parser, the judge,
the classifier's outlier, the sampler and the signing gate.

    python3 -m unittest discover -s factory/tests -t factory
"""

import tempfile
import unittest
import unittest.mock
from pathlib import Path

from earned_trust import classifier, commands, gate, gitdiff, judge, pipeline, sources

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


class GateTests(unittest.TestCase):
    def test_cannot_sign_before_deciding_and_non_owner_cannot_sign(self):
        with tempfile.TemporaryDirectory() as d, unittest.mock.patch.dict("os.environ", {"ET_LEDGER_DIR": d}):
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


if __name__ == "__main__":
    unittest.main()
