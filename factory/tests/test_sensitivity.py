"""Critical code: declared areas and their owners, detectors (deleted lines
too), CODEOWNERS, the situation, and who may sign."""

import tempfile
import unittest
import unittest.mock
from pathlib import Path

from sancho import classifier, commands, config, pipeline, sensitivity, sources

DIFF = """diff --git a/src/Bank/Payments/TransferService.cs b/src/Bank/Payments/TransferService.cs
--- a/src/Bank/Payments/TransferService.cs
+++ b/src/Bank/Payments/TransferService.cs
@@ -1,8 +1,6 @@
 public sealed class TransferService
 {
-    if (amount <= 0) throw new ArgumentOutOfRangeException(nameof(amount));
+    public const double FeeRate = 0.015;
     if (from.Balance < amount) throw new InvalidOperationException();
-    from.Balance -= amount;
+    from.Balance -= amount + (decimal)((double)amount * FeeRate);
     to.Balance += amount;
 }
diff --git a/src/Ui/Label.cs b/src/Ui/Label.cs
--- a/src/Ui/Label.cs
+++ b/src/Ui/Label.cs
@@ -1,1 +1,1 @@
-var text = "Hello";
+var text = "Hi";
"""

SETTINGS = """[review]
generated = []
tests = ['^tests/']
public_api = []
[sensitivity]
ai = false
[[critical]]
name = "payments"
paths = ['^src/Bank/Payments/']
owners = ["ana"]
signatures = 1
"""


def change(diff=DIFF):
    return sources.make("pr-x", {"issue": 0, "sha": "a" * 40, "subject": "fee", "author": "agent"},
                        {"title": "", "body": "", "url": ""}, diff, "test")


class SensitivityTests(unittest.TestCase):
    def tearDown(self):
        config.use(None, "")
        sensitivity.use_base(None)

    def review(self, settings=SETTINGS, codeowners=None, diff=DIFF):
        config.use(settings, "test", codeowners)
        d = Path(tempfile.mkdtemp())
        with unittest.mock.patch.dict("os.environ", {"SANCHO_LEDGER_DIR": str(d)}):
            return pipeline.review(change(diff), use_llm=False, run_dir=d), d

    def test_declared_area_forces_a_full_read_and_names_its_owner(self):
        r, _ = self.review()
        z = r["sensitivity"]["zones"][0]
        self.assertEqual((z["name"], z["owners"], r["router"]["tier"]), ("payments", ["ana"], "T2"))
        self.assertIn("critical operation: payments", r["router"]["reasons"][0])

    def test_detectors_see_floating_point_money_and_removed_checks(self):
        r, _ = self.review()
        ev = {(e["detector"], e["removed"]) for e in r["sensitivity"]["zones"][0]["evidence"]}
        self.assertIn(("money held in floating point", False), ev)
        self.assertIn(("money movement", True), ev)  # the removed `amount <= 0` check

    def test_undeclared_money_code_is_still_detected_with_codeowners_as_owner(self):
        r, _ = self.review(settings="[review]\ngenerated = []\npublic_api = []\n[sensitivity]\nai = false\n",
                           codeowners="/src/Bank/ @luis\n*.md @docs-team/writers\n")
        names = {z["name"]: z for z in r["sensitivity"]["zones"]}
        self.assertIn("money held in floating point", names)
        self.assertEqual(names["money held in floating point"]["owners"], ["luis"])
        self.assertNotIn("src/Ui/Label.cs", r["sensitivity"]["files"])  # a UI string is not critical

    def test_only_the_areas_owner_can_sign(self):
        r, d = self.review()
        commands.apply(r, d, "ana", "/requirements ok \"read it\"", can_sign=True)
        for a in r["abstentions"]:
            commands.apply(r, d, "ana", f"/decide {a['id']} {a['options'][0]} \"x\"", can_sign=True)
        commands.apply(r, d, "ana", "/accept all", can_sign=True)
        _, msg = commands.apply(r, d, "bob", '/sign "Bob"', can_sign=True)
        self.assertIn("its owner signs first: @ana", msg)
        state, msg = commands.apply(r, d, "ana", '/sign "Ana"', can_sign=True)
        self.assertTrue(state["signed_complete"], msg)

    def test_untested_critical_code_is_a_decision_for_its_owner(self):
        r, _ = self.review()
        kinds = [a["kind"] for a in r["abstentions"]]
        self.assertEqual(kinds[:2], ["critical-operation", "critical-untested"])
        self.assertEqual(r["abstentions"][1]["who_decides"], "@ana")

    def test_codeowners_last_matching_line_wins(self):
        text = "* @everyone\n/src/Bank/ @luis\n/src/Bank/Payments/*.cs @ana @org/payments\n"
        self.assertEqual(sensitivity.code_owners("src/Bank/Payments/T.cs", text), (["ana"], ["org/payments"]))
        self.assertEqual(sensitivity.code_owners("src/Bank/Account.cs", text), (["luis"], []))
        self.assertEqual(sensitivity.code_owners("README.md", text), (["everyone"], []))

    def test_two_signatures_when_the_area_asks_for_them(self):
        r, _ = self.review(settings=SETTINGS.replace("owners = [\"ana\"]", "owners = [\"ana\", \"luis\"]")
                           .replace("signatures = 1", "signatures = 2"))
        need, groups = commands.required_signatures(r)
        self.assertEqual((need, groups[0]["owners"]), (2, ["ana", "luis"]))

    def test_the_challenge_prs_have_no_critical_code(self):
        config.use(None, "")
        for b in sources.branches():
            with tempfile.TemporaryDirectory() as d:
                r = pipeline.review(sources.load(b), use_llm=False, run_dir=Path(d), write=False)
            self.assertEqual(r["sensitivity"]["zones"], [], b)

    def test_a_helper_used_by_a_critical_area_is_critical_too(self):
        helper = """diff --git a/src/Bank/Infrastructure/Retry.cs b/src/Bank/Infrastructure/Retry.cs
--- a/src/Bank/Infrastructure/Retry.cs
+++ b/src/Bank/Infrastructure/Retry.cs
@@ -1,3 +1,4 @@
 public static class Retry
 {
-    public static T Run<T>(Func<T> op) => op();
+    public static T Run<T>(Func<T> op, int attempts = 3)
+        => Loop(op, attempts);
 }
"""
        sensitivity.use_base({"src/Bank/Payments/CardGateway.cs":
                              "public sealed class CardGateway\n{\n    public string Charge() => Retry.Run(() => net.Charge());\n}\n",
                              "src/Bank/Other.cs": "Retry.Run(x);"})
        r, _ = self.review(diff=helper)
        z = r["sensitivity"]["zones"][0]
        self.assertEqual((z["name"], z["owners"], r["router"]["tier"]), ("payments (through Retry)", ["ana"], "T2"))
        self.assertEqual((z["caller"]["file"], z["caller"]["line"]), ("src/Bank/Payments/CardGateway.cs", 3))
        self.assertIn("CardGateway.cs:3", r["abstentions"][0]["decision"])

    def test_without_callers_in_the_area_a_helper_is_not_critical(self):
        sensitivity.use_base({"src/Bank/Payments/CardGateway.cs": "public sealed class CardGateway { }\n"})
        r, _ = self.review(diff=DIFF.split("diff --git a/src/Ui")[0].replace("Payments/TransferService", "Ui/Text")
                           .replace("Balance", "Width").replace("amount", "size").replace("double", "int"))
        self.assertEqual(r["sensitivity"]["zones"], [])

    def test_docs_in_a_critical_area_need_their_owner_but_no_tests(self):
        docs = """diff --git a/src/Bank/Payments/README.md b/src/Bank/Payments/README.md
--- a/src/Bank/Payments/README.md
+++ b/src/Bank/Payments/README.md
@@ -1,1 +1,1 @@
-Fees are charged to the sender.
+Fees are charged to the receiver.
"""
        r, _ = self.review(diff=docs)
        self.assertEqual(r["tracer"]["execution"]["status"], "NOT NEEDED")
        self.assertEqual(r["sensitivity"]["required"]["owner_groups"][0]["owners"], ["ana"])
        self.assertNotIn("critical-untested", [a["kind"] for a in r["abstentions"]])

    def test_the_first_of_two_signatures_is_accepted(self):
        r, d = self.review(settings=SETTINGS.replace('owners = ["ana"]', 'owners = ["ana", "luis"]')
                           .replace("signatures = 1", "signatures = 2"))
        commands.apply(r, d, "ana", '/requirements ok "read it"', can_sign=True)
        for a in r["abstentions"]:
            commands.apply(r, d, "ana", f"/decide {a['id']} {a['options'][0]} \"x\"", can_sign=True)
        commands.apply(r, d, "ana", "/accept all", can_sign=True)
        state, msg = commands.apply(r, d, "ana", '/sign "Ana"', can_sign=True)
        self.assertEqual(len(state["signatures"]), 1, msg)
        self.assertFalse(state.get("signed_complete"))
        state, msg = commands.apply(r, d, "luis", '/sign "Luis"', can_sign=True)
        self.assertTrue(state["signed_complete"], msg)

    def sign_ready(self, r, d, option=0):
        commands.apply(r, d, "ana", '/requirements ok "read it"', can_sign=True)
        for ab in r["abstentions"]:
            commands.apply(r, d, "ana", f'/decide {ab["id"]} {ab["options"][option]} "x"', can_sign=True)
        commands.apply(r, d, "ana", "/accept all", can_sign=True)

    def test_a_second_signature_can_come_from_anyone_with_write_access(self):
        r, d = self.review()
        r["router"]["second_reviewer"] = True  # e.g. T2 in a folder whose trust is revoked
        self.sign_ready(r, d)
        _, msg = commands.apply(r, d, "luis", '/sign "Luis"', can_sign=True)
        self.assertIn("its owner signs first: @ana", msg)  # not before the owner
        state, _ = commands.apply(r, d, "ana", '/sign "Ana"', can_sign=True)
        self.assertFalse(state.get("signed_complete"))
        state, msg = commands.apply(r, d, "luis", '/sign "Luis"', can_sign=True)
        self.assertTrue(state["signed_complete"], msg)

    def test_a_no_to_a_decision_blocks_the_signature(self):
        r, d = self.review()
        self.sign_ready(r, d, option=-1)  # request-changes, wait-for-tests
        state, msg = commands.apply(r, d, "ana", '/sign "Ana"', can_sign=True)
        self.assertEqual(state["signatures"], [])
        self.assertIn("was answered `request-changes`", msg)
        commands.apply(r, d, "ana", f'/decide {r["abstentions"][0]["id"]} approve "fixed by talking"', can_sign=True)
        commands.apply(r, d, "ana", f'/decide {r["abstentions"][1]["id"]} merge-without-tests "x"', can_sign=True)
        state, msg = commands.apply(r, d, "ana", '/sign "Ana"', can_sign=True)
        self.assertTrue(state["signed_complete"], msg)

    def test_tests_that_run_in_the_repositorys_ci_are_not_untested(self):
        config.use(SETTINGS, "test")
        c = change()
        cl = classifier.run(c)
        trace = {"execution": {"status": "NOT RUN", "why": "never run here", "elsewhere": True}}
        out = sensitivity.run(c, cl, trace, use_llm=False)
        self.assertEqual([e["rule"] for e in out["escalations"]], ["CRITICAL-TESTS-IN-CI"])

    def test_no_ai_question_about_a_diff_with_no_code(self):
        docs = sources.make("pr-d", {"issue": 0, "sha": "b" * 40, "subject": "docs", "author": "x"},
                            {"title": "", "body": "", "url": ""},
                            "diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-a\n+b\n", "t")
        with unittest.mock.patch("sancho.llm.chat", side_effect=AssertionError("called")):
            _, ai = sensitivity.ask_ai(docs, classifier.run(docs), offline=True)
        self.assertEqual(ai["status"], "SKIPPED")

    def test_one_signature_line_per_set_of_owners(self):
        r, _ = self.review(codeowners="* @ana\n", diff=DIFF.replace('+var text = "Hi";', '+var password = "Hi";'))
        self.assertGreater(len(r["sensitivity"]["required"]["owner_groups"]), 1)
        sign = [i["what"] for i in commands.todo(r, {"signatures": [], "decisions": {}, "findings": {}})
                if i["what"].startswith("Signature")]
        self.assertEqual(len(sign), 1, sign)
        self.assertIn("payments", sign[0])

    def test_a_bad_critical_area_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "needs a name and paths"):
            config.parse("[[critical]]\nname = \"x\"\n")


if __name__ == "__main__":
    unittest.main()
