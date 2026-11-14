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


if __name__ == "__main__":
    unittest.main()
