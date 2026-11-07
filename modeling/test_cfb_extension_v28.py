"""Source-scoped NCAA timing tests; these do not certify forecasting pace."""
import unittest
from .fullgame_v23.rules import RegulationClock,cfb_period_extension
SOURCE={'source':'https://official.example.test/gamebook','sourceVersion':'synthetic-ruling'}
class ExtensionTests(unittest.TestCase):
    def test_first_and_third_quarter_enforcement_carries_forward(self):
        for q in (1,3):
            c=RegulationClock('CFB',2024,period=q,remaining=0);r=c.request_period_extension('accepted_live_ball_foul',SOURCE);self.assertFalse(r['untimedDown']);self.assertTrue(r['carryEnforcementToNextPeriod']);c.next_period()
    def test_half_cannot_end_before_required_untimed_down(self):
        c=RegulationClock('CFB',2024,period=2,remaining=0);r=c.request_period_extension('offsetting_fouls',SOURCE);self.assertIsNone(r['physicalPlayDuration'])
        with self.assertRaises(ValueError):c.next_period()
        with self.assertRaises(ValueError):c.advance(1)
        c.complete_untimed_down();c.next_period();self.assertEqual(c.period,3)
    def test_repeated_untimed_foul_does_not_skip_the_period(self):
        c=RegulationClock('CFB',2023,period=4,remaining=0);c.request_period_extension('inadvertent_whistle',SOURCE);c.complete_untimed_down(repeat_reason='offsetting_fouls',source=SOURCE)
        self.assertTrue(c.pending_untimed_down);c.complete_untimed_down();self.assertFalse(c.pending_untimed_down)
    def test_uncertified_seasons_elections_and_missing_sources_withheld(self):
        for year in (2022,2025,2026):
            with self.assertRaises(ValueError):cfb_period_extension(year,2,'offsetting_fouls')
        with self.assertRaises(ValueError):cfb_period_extension(2024,2,'accepted_live_ball_foul',loss_of_down=True)
        with self.assertRaises(ValueError):RegulationClock('CFB',2024,period=2,remaining=0).request_period_extension('offsetting_fouls',{})
    def test_nba_and_nfl_cannot_use_ncaa_extension(self):
        for sport in ('NBA','NFL'):
            with self.assertRaises(ValueError):RegulationClock(sport,2024,remaining=0).request_period_extension('offsetting_fouls',SOURCE)
