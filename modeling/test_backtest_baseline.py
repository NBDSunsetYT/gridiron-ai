"""Synthetic statistical pipeline checks; real audit report provenance is separate."""
import csv
import io
import unittest
from modeling.backtest_baseline import evaluate


def fixture():
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['game_id','season','gameday','home_score','away_score','game_type','week'])
    writer.writeheader()
    for season in (2023, 2024):
        for i in range(120):
            writer.writerow({'game_id': f'SYNTH-{season}-{i}', 'season': season,
                'gameday': f'{season}-10-{1+i//10:02}', 'home_score': 20+i%5,
                'away_score': 20+i%4, 'game_type': 'REG', 'week': i//10+1})
    return output.getvalue()


class BaselineTests(unittest.TestCase):
    def test_chronological_validation_never_uses_same_date_scores(self):
        report = evaluate(fixture(), 45.5, 2023, 2024, 'SYNTHETIC PIPELINE TEST ONLY')
        self.assertEqual(report['n'], 120)
        self.assertEqual(report['trainingGamesAtStart'], 120)
        self.assertEqual(sum(row['n'] for row in report['calibration']), 120)
        self.assertGreaterEqual(report['brier'], 0)
        self.assertLessEqual(report['brier'], 1)
        self.assertEqual(report['marketBenchmark'], None)
        self.assertIn('same-date outcomes excluded', report['validation'])

    def test_invalid_or_insufficient_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(fixture(), 45.5, 2024, 2023, 'SYNTHETIC')
        with self.assertRaises(ValueError):
            evaluate('game_id\nSYNTH\n', 45.5, 2023, 2024, 'SYNTHETIC')


if __name__ == '__main__':
    unittest.main()
