"""Source/accounting parsing tests, not predictive accuracy evidence."""
import unittest,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v26_forecast_test',ROOT/'scripts/v26-forecast.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ProspectiveInputs(unittest.TestCase):
    def test_missing_stats_are_not_zero_and_minutes_preserve_precision(self):
        self.assertIsNone(module.number('DNP'));self.assertIsNone(module.number('--'))
        self.assertEqual(module.number('31:30'),31.5)
        self.assertEqual(module.parse_line(['minutes','points'],['--','0']),{'points':0.})
    def test_football_attempts_and_negative_ncaa_yards_are_explicit(self):
        r=module.parse_line(['completions/passingAttempts','passingYards','rushingYards'],['18/30','200','-7'])
        self.assertEqual(r,{'passingCompletions':18.,'passingAttempts':30.,'passingYards':200.,'rushingYards':-7.})
    def test_combined_stats_derive_from_same_player_row(self):
        r=module.parse_line(['points','rebounds','assists','threePointFieldGoalsMade-threePointFieldGoalsAttempted'],['20','8','5','3-7'])
        self.assertEqual(r['pointsReboundsAssists'],33);self.assertEqual(r['threePointersMade'],3)
        self.assertEqual(r['threePointAttempts'],7)
    def test_final_box_active_false_is_not_a_pregame_injury(self):
        data={'header':{'id':'OLD','competitions':[{'date':'2026-11-01T00:00Z','status':{'type':{'completed':True}},'competitors':[{'team':{'id':'A'},'score':'100'},{'team':{'id':'B'},'score':'90'}]}]},'boxscore':{'players':[{'team':{'id':'A'},'statistics':[{'keys':['minutes','points'],'athletes':[{'athlete':{'id':'p','displayName':'SYNTHETIC'},'active':False,'didNotPlay':False,'stats':['30','20']}],'totals':['240','100']}]}]}}
        r=module.normalized(data,'NBA');self.assertEqual(r['teams']['A']['players']['p']['stats']['minutes'],30)
        data['header']['competitions'][0]['status']['type']['completed']=False
        with self.assertRaises(ValueError):module.normalized(data,'NBA')


if __name__=='__main__':unittest.main()
