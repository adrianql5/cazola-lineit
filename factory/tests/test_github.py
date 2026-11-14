"""The GitHub Actions entry point against a fake GitHub API: a PR event posts
the brief and a blocked check; PR comments replayed in order open the gate."""

import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from earned_trust import github, pipeline, sources

COMMIT_AT = "2026-11-14T10:00:00Z"


class FakeGitHub:
    def __init__(self, comments):
        self.comments = comments
        self.posted, self.checks = [], []
        self.diff = sources.load("ju26-issue-2283").diff_text

    def __call__(self, method, path, body=None, accept=""):
        if accept.endswith("diff"):
            return self.diff
        if "/issues/7/comments?" in path:
            return self.comments
        if path.endswith("/pulls/7"):
            return PR
        if "/commits/" in path:
            return {"commit": {"committer": {"date": COMMIT_AT}}}
        if path.endswith("/check-runs"):
            self.checks.append(body)
            return {}
        if method in ("POST", "PATCH") and "comments" in path:
            self.posted.append(body["body"])
            return {}
        return {}


PR = {"number": 7, "title": "implementation for #2283", "body": "", "user": {"login": "agent"},
      "head": {"ref": "ju26-issue-2283", "sha": "b" * 40}, "html_url": "https://github.com/me/mp/pull/7"}


def comment(login, text, at, assoc="OWNER"):
    return {"id": hash(text) % 10000, "body": text, "created_at": at, "author_association": assoc,
            "user": {"login": login, "type": "User"}}


class GitHubActionTests(unittest.TestCase):
    def run_event(self, name, event, comments):
        fake = FakeGitHub(comments)
        with tempfile.TemporaryDirectory() as d:
            ev = Path(d) / "event.json"
            ev.write_text(json.dumps(event))
            env = {"GITHUB_EVENT_PATH": str(ev), "GITHUB_EVENT_NAME": name, "GITHUB_REPOSITORY": "me/mp",
                   "GITHUB_TOKEN": "t", "ET_LEDGER_DIR": d}
            with unittest.mock.patch.object(github, "gh", fake), \
                    unittest.mock.patch.object(pipeline, "RUNS", Path(d) / "runs"), \
                    unittest.mock.patch.dict(os.environ, env):
                env.pop("GITHUB_STEP_SUMMARY", None)
                github.main(None)
        return fake

    def test_pull_request_posts_brief_and_blocks(self):
        fake = self.run_event("pull_request", {"pull_request": PR}, [])
        self.assertIn("Earned-Trust Evidence Brief", fake.posted[0])
        self.assertEqual(fake.checks[-1]["conclusion"], "action_required")
        self.assertEqual(fake.checks[-1]["name"], github.CHECK)

    def test_commands_replayed_in_order_open_the_gate(self):
        comments = [
            comment("old", '/sign "Too Early"', "2026-11-14T09:00:00Z"),  # before the last commit: ignored
            comment("owner", '/decide ABS-1 narrow-to-metadata-types "keep own diagnostics"\n/accept P-GLOBAL-WRAP', "2026-11-14T10:05:00Z"),
            comment("drive-by", '/sign "Drive By"', "2026-11-14T10:06:00Z", assoc="NONE"),
            comment("owner", '/sign "The Owner"', "2026-11-14T10:07:00Z"),
        ]
        ev = {"issue": {"number": 7, "pull_request": {}}, "comment": comments[-1]}
        fake = self.run_event("issue_comment", ev, comments)
        self.assertEqual(fake.checks[-1]["conclusion"], "success")
        self.assertIn("Accountability Receipt", fake.checks[-1]["output"]["text"])
        log = fake.posted[-1]
        self.assertIn("written before the last commit", log)
        self.assertIn("drive-by is not an owner", log)
        self.assertIn("Signed by The Owner", log)


if __name__ == "__main__":
    unittest.main()
