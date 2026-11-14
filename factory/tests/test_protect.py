"""The merge gate set up by protect.py: created once, then updated in place,
also when an earlier hand-made ruleset already requires the gate check."""

import os
import unittest
import unittest.mock

from sancho import github, protect


class FakeGitHub:
    def __init__(self, existing):
        self.existing, self.calls = existing, []

    def __call__(self, method, path, body=None, accept=""):
        self.calls.append((method, path, body))
        if method == "GET" and path.endswith("/rulesets"):
            # like GitHub: the list has no rules in it
            return [{k: v for k, v in r.items() if k != "rules"} for r in self.existing]
        if method == "GET":
            return next(r for r in self.existing if path.endswith(f"/rulesets/{r['id']}"))
        if method == "POST":
            return {"id": 99}
        return {}


class ProtectTests(unittest.TestCase):
    def run_with(self, existing, branches=()):
        fake = FakeGitHub(existing)
        with unittest.mock.patch.object(github, "gh", fake), unittest.mock.patch.dict(os.environ, {"GITHUB_TOKEN": "t"}):
            out = protect.main("me/r", list(branches))
        return fake, out

    def test_creates_the_ruleset_when_there_is_none(self):
        fake, out = self.run_with([])
        method, path, body = fake.calls[-1]
        self.assertEqual((method, path, out["id"]), ("POST", "/repos/me/r/rulesets", 99))
        checks = next(r for r in body["rules"] if r["type"] == "required_status_checks")["parameters"]["required_status_checks"]
        self.assertEqual(checks, [{"context": github.CHECK, "integration_id": 15368}])
        self.assertEqual(body["bypass_actors"], [])

    def test_updates_a_hand_made_ruleset_that_requires_the_gate(self):
        hand = {"id": 7, "name": "Ernet Trust Gate", "rules": [{"type": "required_status_checks", "parameters": {
            "required_status_checks": [{"context": github.CHECK}]}}]}
        other = {"id": 8, "name": "something else", "rules": []}
        fake, out = self.run_with([other, hand], branches=["ju26-base"])
        method, path, body = fake.calls[-1]
        self.assertEqual((method, path), ("PUT", "/repos/me/r/rulesets/7"))
        self.assertEqual(body["name"], protect.NAME)
        self.assertEqual(body["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH", "refs/heads/ju26-base"])


if __name__ == "__main__":
    unittest.main()
