"""Per-repository settings (.sancho.toml): parsing, mistakes that must
not pass silently, and their effect on the review."""

import unittest

from sancho import classifier, config, sources


class ConfigTests(unittest.TestCase):
    def tearDown(self):
        config.use(None, "")

    def test_defaults_without_a_file(self):
        cfg = config.use(None, "")
        self.assertFalse(cfg["gate"]["merge_on_sign"])
        self.assertEqual(cfg["review"]["sample_rate"], 0.05)

    def test_a_typo_is_an_error_not_a_silent_default(self):
        with self.assertRaisesRegex(ValueError, "unknown setting gate.merge_on_sing"):
            config.parse("[gate]\nmerge_on_sing = true\n")
        with self.assertRaisesRegex(ValueError, "must be bool"):
            config.parse('[gate]\nmerge_on_sign = "yes"\n')
        with self.assertRaisesRegex(ValueError, "merge_method"):
            config.parse('[gate]\nmerge_method = "fast"\n')

    def test_settings_change_what_counts_as_generated(self):
        change = sources.load("ju26-issue-2297")
        self.assertEqual(classifier.run(change)["snapshots"], 222)
        config.use("[review]\ngenerated = []\n", "test")
        r = classifier.run(change)
        self.assertEqual((r["snapshots"], r["outliers"]), (0, []))  # nothing is generated now: no pattern to hide

    def test_settings_are_pinned_in_the_receipts_hash(self):
        config.use(None, "")
        empty = config.digest()
        config.use("[gate]\nmerge_on_sign = true\n", "test")
        self.assertNotEqual(config.digest(), empty)


class UpstreamHistoryTests(unittest.TestCase):
    """MessagePack-CSharp's history sets folder trust only for MessagePack."""

    def tearDown(self):
        config.use(None, "")

    def test_defaults_use_it_another_repository_does_not(self):
        from sancho import ledger
        config.use(None, "")
        self.assertEqual(ledger.states_for(["README.md"], ledger.trust_table())["README.md"]["state"], "REVOKED")
        config.use("[gate]\nmerge_on_sign = true\n", "test")
        self.assertFalse(config.upstream_history())
        self.assertEqual(ledger.states_for(["README.md"], ledger.trust_table())["README.md"]["state"], "PROBATION")
        config.use("[trust]\nupstream_history = \"on\"\n", "test")
        self.assertTrue(config.upstream_history())

    def test_a_bad_value_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "auto, on or off"):
            config.parse("[trust]\nupstream_history = \"yes\"\n")


if __name__ == "__main__":
    unittest.main()
