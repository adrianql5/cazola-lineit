"""Live measurements from a fake GitHub: one PR whose brief carries the hidden
metrics block (signed), one older brief read from its text, its comments and
the gate check."""

import json
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

from earned_trust import github, live

SIGNED = {
    "v": 1, "pr": 8, "title": "Add ExcludeFromCodeCoverage", "sha": "a" * 40,
    "pr_opened_at": "2026-11-14T09:00:00Z", "brief_published_at": "2026-11-14T10:00:00Z",
    "tier": "T1", "lines_total": 1392, "lines_must_read": 42, "files_total": 237, "files_must_read": 10,
    "findings": [{"id": "SCOPE-1", "source": "rules"}, {"id": "LLM-1", "source": "ai"}],
    "answers": [{"id": "SCOPE-1", "verdict": "accepted", "by": "owner", "at": "2026-11-14T10:10:00Z", "source": "rules"},
                {"id": "LLM-1", "verdict": "refuted", "by": "owner", "at": "2026-11-14T10:11:00Z", "source": "ai"}],
    "decisions": [], "abstentions": 1, "gate": "success", "signed_at": "2026-11-14T10:12:00Z", "signers": ["owner"],
}

OLD_BRIEF = """### 🔎 Earned-Trust review · full read needed (1,043 lines)

**Read:** everything (1,035 lines), because it adds public API.

**P-TEST-EXCLUDED** · `x.csproj:14`
claim
**LLM-1** · `Gen.cs:70`
claim
"""


def pr(n, merged=None):
    return {"number": n, "title": f"PR {n}", "state": "open", "created_at": "2026-11-14T09:00:00Z",
            "merged_at": merged, "head": {"sha": f"{n}" * 40}, "html_url": f"https://github.com/me/r/pull/{n}"}


def comment(body, at, login="owner", assoc="OWNER", type_="User"):
    return {"id": hash(body) % 1000, "body": body, "created_at": at, "author_association": assoc,
            "user": {"login": login, "type": type_}}


class FakeGitHub:
    def __call__(self, method, path, body=None, accept=""):
        if path.startswith("/repos/me/r/pulls?state=all"):
            return [pr(8, merged="2026-11-14T11:00:00Z"), pr(2), pr(5)]
        if "/issues/8/comments" in path:
            return [comment(f"{github.MARK}\n<!-- earned-trust-metrics {json.dumps(SIGNED)} -->\nbrief", "2026-11-14T10:00:00Z", "bot", "NONE", "Bot")]
        if "/issues/2/comments" in path:
            return [comment(f"{github.MARK}\n{OLD_BRIEF}", "2026-11-14T10:00:00Z", "bot", "NONE", "Bot"),
                    comment("/accept P-TEST-EXCLUDED", "2026-11-14T10:20:00Z"),
                    comment("/refute LLM-1 \"wrong\"", "2026-11-14T10:21:00Z", login="drive-by", assoc="NONE"),
                    comment("/refute LLM-1 \"wrong\"", "2026-11-14T10:22:00Z")]
        if "/issues/5/comments" in path:
            return [comment("a normal PR, never reviewed", "2026-11-14T10:00:00Z")]
        if "/pulls/2/comments" in path:
            return []
        if path.endswith("/commits/" + "2" * 40):
            return {"commit": {"committer": {"date": "2026-11-14T09:30:00Z"}}}
        if "/check-runs" in path:
            return {"check_runs": [{"conclusion": "success", "completed_at": "2026-11-14T10:40:00Z"}]}
        if "/issues?state=all" in path:
            return []
        raise AssertionError(path)


class LiveTests(unittest.TestCase):
    def setUp(self):
        with unittest.mock.patch.object(github, "gh", FakeGitHub()):
            self.d = live.collect("me/r")
        self.rows = {r["pr"]: r for r in self.d["prs"]}

    def test_only_reviewed_prs_count(self):
        self.assertEqual(sorted(self.rows), [2, 8])

    def test_signed_pr_from_the_hidden_block(self):
        r = self.rows[8]
        self.assertEqual((r["minutes_to_sign"], r["minutes_to_merge"]), (12.0, 120.0))

    def test_old_brief_read_from_text_comments_and_check(self):
        r = self.rows[2]
        self.assertEqual((r["tier"], r["lines_must_read"], r["lines_total"]), ("T2", 1035, 1043))
        self.assertEqual({a["id"]: a["verdict"] for a in r["answers"]}, {"P-TEST-EXCLUDED": "accepted", "LLM-1": "refuted"})
        self.assertEqual(r["minutes_to_sign"], 40.0)  # brief at 10:00, gate green at 10:40

    def test_minutes_are_utc_whatever_the_local_timezone(self):
        # 4 hours across the end of summer time in Europe; mktime read them as local time
        with unittest.mock.patch.dict("os.environ", {"TZ": "Europe/Madrid"}):
            time.tzset()
            got = live.minutes("2026-10-25T00:00:00Z", "2026-10-25T04:00:00Z")
        time.tzset()
        self.assertEqual(got, 240.0)

    def test_summary_splits_rules_and_ai(self):
        s = self.d["summary"]
        self.assertEqual(s["answers"]["rules"], {"accepted": 2, "refuted": 0, "open": 0, "acceptance_rate": 1.0})
        self.assertEqual(s["answers"]["ai"], {"accepted": 0, "refuted": 2, "open": 0, "acceptance_rate": 0.0})
        self.assertEqual((s["lines_to_humans"], s["lines_total"]), (42 + 1035, 1392 + 1043))
        self.assertEqual((s["signed"], s["median_minutes_to_sign"]), (2, 26.0))


class MetricsBlockTests(unittest.TestCase):
    def test_a_signed_review_writes_its_numbers(self):
        from tests.test_github import GitHubActionTests, comment as c
        t = GitHubActionTests()
        comments = [c("owner", '/decide ABS-1 narrow-to-metadata-types "x"\n/accept P-GLOBAL-WRAP\n/sign "The Owner"',
                      "2026-11-14T10:05:00Z")]
        fake = t.run_event("issue_comment", {"issue": {"number": 7, "pull_request": {}}, "comment": comments[0]}, comments)
        brief = next(p for p in reversed(fake.posted) if github.MARK in p)
        m = json.loads(github.METRICS.search(brief).group(1))
        self.assertEqual((m["gate"], m["signed_at"], m["tier"]), ("success", "2026-11-14T10:05:00Z", "T1"))
        self.assertEqual(m["answers"][0]["id"], "P-GLOBAL-WRAP")
        self.assertEqual(m["answers"][0]["source"], "rules")


if __name__ == "__main__":
    unittest.main()
