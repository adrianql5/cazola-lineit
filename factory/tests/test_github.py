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
    def __init__(self, comments, names=None):
        self.comments = comments
<<<<<<< Updated upstream
        self.posted, self.checks, self.reviews, self.replies = [], [], [], []
=======
        self.names = names or {}  # login -> the name on the GitHub profile
        self.posted, self.checks, self.reviews, self.replies, self.reactions = [], [], [], [], []
>>>>>>> Stashed changes
        self.diff = sources.load("ju26-issue-2283").diff_text

    def __call__(self, method, path, body=None, accept=""):
        if accept.endswith("diff"):
            return self.diff
        if "/issues/7/comments?" in path:
            return [c for c in self.comments if c.get("kind") != "review"]
        if "/pulls/7/comments?" in path:
            return [c for c in self.comments if c.get("kind") == "review"]
        if "/issues?state=all" in path:
            return []
        if path.endswith("/reviews"):
            self.reviews.append(body)
            return {}
        if path.endswith("/replies"):
            self.replies.append(body["body"])
            return {}
        if path.endswith("/pulls/7"):
            return PR
        if path.startswith("/users/"):
            return {"login": path[len("/users/"):], "name": self.names.get(path[len("/users/"):])}
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
    def run_event(self, name, event, comments, names=None):
        fake = FakeGitHub(comments, names)
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
        self.assertIn("Earned-Trust review", fake.posted[0])
        # each finding also lands on its line in "Files changed"
        self.assertEqual([c["body"].split("**")[1] for c in fake.reviews[0]["comments"]], ["P-GLOBAL-WRAP"])
        self.assertEqual(fake.reviews[0]["comments"][0]["side"], "RIGHT")
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
        self.assertIn("Receipt ·", fake.checks[-1]["output"]["text"])
        self.assertEqual(fake.checks[-1]["output"]["title"], "Signed by The Owner")
        brief_text = next(p for p in reversed(fake.posted) if github.MARK in p)
        self.assertIn("written before the latest commit", brief_text)
        self.assertIn("@drive-by can't sign", brief_text)
        # the comment that triggered the run gets its own answer
        self.assertIn("Signed by The Owner", fake.posted[-1])
        self.assertTrue(fake.posted[-1].startswith('> /sign "The Owner"'))

    def test_a_bare_sign_uses_the_name_on_the_github_profile(self):
        comments = [
            comment("owner", '/decide ABS-1 narrow-to-metadata-types "x"\n/accept P-GLOBAL-WRAP', "2026-11-14T10:05:00Z"),
            comment("owner", "/sign", "2026-11-14T10:07:00Z"),
        ]
        ev = {"issue": {"number": 7, "pull_request": {}}, "comment": comments[-1]}
        fake = self.run_event("issue_comment", ev, comments, names={"owner": "Ana O'Neill"})
        self.assertEqual(fake.checks[-1]["conclusion"], "success")
        self.assertEqual(fake.checks[-1]["output"]["title"], "Signed by Ana O'Neill")

    def test_a_bare_sign_without_a_profile_name_asks_for_it(self):
        comments = [
            comment("owner", '/decide ABS-1 narrow-to-metadata-types "x"\n/accept P-GLOBAL-WRAP', "2026-11-14T10:05:00Z"),
            comment("owner", "/sign", "2026-11-14T10:07:00Z"),
        ]
        ev = {"issue": {"number": 7, "pull_request": {}}, "comment": comments[-1]}
        fake = self.run_event("issue_comment", ev, comments)
        self.assertEqual(fake.checks[-1]["conclusion"], "action_required")
        self.assertIn("Your GitHub profile has no name", fake.posted[-1])

    def test_command_in_a_line_comment_gets_a_reply_in_its_thread(self):
        c = comment("owner", "/explain P-GLOBAL-WRAP", "2026-11-14T10:05:00Z")
        c["kind"] = "review"
        ev = {"pull_request": PR, "comment": c}
        fake = self.run_event("pull_request_review_comment", ev, [c])
        self.assertIn("Who raised it", fake.replies[-1])


if __name__ == "__main__":
    unittest.main()
