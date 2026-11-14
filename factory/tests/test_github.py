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
        self.posted, self.checks, self.reviews, self.replies, self.reactions = [], [], [], [], []
        self.merges, self.dispatches, self.settings = [], [], None
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
        if path.endswith("/reactions"):
            self.reactions.append((path, body["content"]))
            return {}
        if path.endswith("/replies"):
            self.replies.append(body["body"])
            return {}
        if path.endswith("/pulls/7"):
            return PR
        if "/commits/" in path:
            return {"commit": {"committer": {"date": COMMIT_AT}}}
        if "/contents/.earned-trust.toml" in path:
            if self.settings is None:
                raise RuntimeError("404")
            import base64
            return {"content": base64.b64encode(self.settings.encode()).decode()}
        if path.endswith("/merge"):
            self.merges.append(body)
            return {"merged": True}
        if path.endswith("/dispatches"):
            self.dispatches.append(path)
            return {}
        if path == "/repos/me/mp":
            return {"default_branch": "main"}
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
    def run_event(self, name, event, comments, settings=None):
        fake = FakeGitHub(comments)
        fake.settings = settings
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
        # the comment with the commands got a 👍 as soon as it was read
        self.assertEqual(fake.reactions, [(f"/repos/me/mp/issues/comments/{comments[-1]['id']}/reactions", "+1")])

    def test_command_in_a_line_comment_gets_a_reply_in_its_thread(self):
        c = comment("owner", "/explain P-GLOBAL-WRAP", "2026-11-14T10:05:00Z")
        c["kind"] = "review"
        ev = {"pull_request": PR, "comment": c}
        fake = self.run_event("pull_request_review_comment", ev, [c])
        self.assertIn("Who raised it", fake.replies[-1])
        self.assertEqual(fake.reactions, [(f"/repos/me/mp/pulls/comments/{c['id']}/reactions", "+1")])

    def test_in_a_findings_thread_the_id_can_be_left_out(self):
        root = {**comment("github-actions", github.FINDING_MARK.format(id="P-GLOBAL-WRAP", sha="b" * 12) + "\n**P-GLOBAL-WRAP**",
                          "2026-11-14T10:01:00Z", assoc="NONE"), "user": {"login": "github-actions[bot]", "type": "Bot"}}
        explain = {**comment("owner", "/explain", "2026-11-14T10:05:00Z"), "in_reply_to_id": root["id"]}
        refute = {**comment("owner", '/refute "the guard is on purpose"', "2026-11-14T10:06:00Z"), "in_reply_to_id": root["id"]}
        for c in (root, explain, refute):
            c["kind"] = "review"
        fake = self.run_event("pull_request_review_comment", {"pull_request": PR, "comment": explain}, [root, explain, refute])
        self.assertIn("Who raised it", fake.replies[-1])
        brief_text = next(p for p in reversed(fake.posted) if github.MARK in p)
        self.assertIn("P-GLOBAL-WRAP refuted by @owner", brief_text)

    def test_with_finding_fills_in_only_what_is_missing(self):
        ids = {"SCOPE-1", "SCOPE-3"}
        self.assertEqual(github.with_finding("/accept", "SCOPE-3", ids), "/accept SCOPE-3")
        self.assertEqual(github.with_finding('/refute "why"', "SCOPE-3", ids), '/refute SCOPE-3 "why"')
        self.assertEqual(github.with_finding("/accept SCOPE-1", "SCOPE-3", ids), "/accept SCOPE-1")
        self.assertEqual(github.with_finding("/accept all", "SCOPE-3", ids), "/accept all")
        self.assertEqual(github.with_finding('/sign "Me"', "SCOPE-3", ids), '/sign "Me"')
        self.assertEqual(github.with_finding("/accept", None, ids), "/accept")  # not in a finding's thread

    def test_reset_makes_earlier_commands_stop_counting(self):
        signed = [
            comment("owner", '/decide ABS-1 narrow-to-metadata-types "x"\n/accept P-GLOBAL-WRAP\n/sign "The Owner"', "2026-11-14T10:05:00Z"),
            {**comment("github-actions", github.RESET_MARK + "\nrestarted", "2026-11-14T10:30:00Z", assoc="NONE"),
             "user": {"login": "github-actions[bot]", "type": "Bot"}},
        ]
        fake = FakeGitHub(signed)
        with tempfile.TemporaryDirectory() as d:
            env = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": "me/mp", "GITHUB_TOKEN": "t", "ET_LEDGER_DIR": d}
            with unittest.mock.patch.object(github, "gh", fake), \
                    unittest.mock.patch.object(pipeline, "RUNS", Path(d) / "runs"), \
                    unittest.mock.patch.dict(os.environ, env):
                github.main(None, reset_pr=7)
        self.assertTrue(any(github.RESET_MARK in p for p in fake.posted))  # the marker comment
        self.assertEqual(fake.checks[-1]["conclusion"], "action_required")
        brief = next(p for p in reversed(fake.posted) if github.MARK in p)
        self.assertIn("To merge, reply to this PR with", brief)


    def test_saved_ai_answers_are_found_without_llm_model_set(self):
        import hashlib
        from earned_trust import llm, prosecutor
        with tempfile.TemporaryDirectory() as d, unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LLM_MODEL", None)
            cache = Path(d) / "llm"
            record = {"model": "qwen3.8-27b", "prompt_version": "v", "input_sha256": "x", "content": "[]"}
            key = hashlib.sha256(b"v\nqwen3.8-27b\nS\nU").hexdigest()
            body = '<!-- earned-trust-llm ' + json.dumps({"sha": "s", "answers": {f"{key[:16]}-v.json": record}}) + ' -->'
            github.restore_llm(body, "s", cache)
            self.assertEqual(llm.chat("S", "U", prompt_version="v", cache_dir=cache, offline=True)["content"], "[]")


    def test_pull_request_target_reviews_without_the_prs_code(self):
        # PRs to main from forks: no checkout (target is None), still the brief, the line comments and the gate
        fake = self.run_event("pull_request_target", {"pull_request": PR}, [])
        self.assertIn("Earned-Trust review", fake.posted[0])
        self.assertTrue(fake.reviews and fake.reviews[0]["comments"])
        self.assertEqual(fake.checks[-1]["conclusion"], "action_required")
        self.assertIn("never runs the PR's code", fake.posted[0])


    def signed_with(self, settings):
        comments = [comment("owner", '/decide ABS-1 narrow-to-metadata-types "x"\n/accept P-GLOBAL-WRAP\n/sign "The Owner"',
                            "2026-11-14T10:05:00Z")]
        pr = {**PR, "base": {"ref": "main"}, "state": "open"}
        with unittest.mock.patch.dict(PR, pr):
            return self.run_event("issue_comment", {"issue": {"number": 7, "pull_request": {}}, "comment": comments[0]},
                                  comments, settings=settings)

    def test_signing_merges_when_the_base_branch_settings_ask_for_it(self):
        fake = self.signed_with('[gate]\nmerge_on_sign = true\nmerge_method = "squash"\n')
        self.assertEqual(fake.checks[-1]["conclusion"], "success")
        self.assertEqual(fake.merges[0]["merge_method"], "squash")
        self.assertIn("signed by The Owner", fake.merges[0]["commit_title"])
        self.assertEqual(fake.dispatches, ["/repos/me/mp/actions/workflows/ci.yml/dispatches"])
        self.assertIn("Merged into `main`", fake.posted[-1])

    def test_signing_does_not_merge_by_default(self):
        fake = self.signed_with(None)  # no settings file: the defaults, merge_on_sign = false
        self.assertEqual(fake.checks[-1]["conclusion"], "success")
        self.assertEqual(fake.merges, [])


if __name__ == "__main__":
    unittest.main()
