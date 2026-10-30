import unittest
from datetime import datetime, timedelta, timezone
from modeling.pipeline import analyze


class PipelineTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        self.rows = [{"observed_at": (start + timedelta(days=i)).isoformat(), "value": 80 if i % 3 == 0 else 40} for i in range(60)]

    def test_rolling_origin_and_metrics(self):
        result = analyze(self.rows, 60, "over", -110, "test fixture, not NFL data")
        first = result["predictions"][0]
        self.assertEqual(first["index"], 20)
        self.assertAlmostEqual(first["probability"], (7 + 0.5) / 21)
        self.assertEqual(result["out_of_sample"]["n"], 40)
        self.assertTrue(0 <= result["out_of_sample"]["brier"] <= 1)

    def test_lookahead_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, "cutoff"):
            analyze(self.rows, 60, "over", -110, "fixture", datetime(2020, 1, 20, tzinfo=timezone.utc))

    def test_unordered_rows_rejected(self):
        with self.assertRaisesRegex(ValueError, "increasing"):
            analyze(list(reversed(self.rows)), 60, "over", -110, "fixture")

    def test_zero_profit_at_fair_price(self):
        for i, row in enumerate(self.rows):
            row["value"] = 80 if i % 2 == 0 else 40
        self.assertEqual(analyze(self.rows, 60, "over", 100, "fixture")["expected_value_per_dollar"], 0)


if __name__ == "__main__":
    unittest.main()
