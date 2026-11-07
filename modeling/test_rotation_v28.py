"""Synthetic software checks; real accuracy belongs to frozen experiments."""
import unittest,copy
import numpy as np
from .fullgame_v23.rotation import MinutesPrior,draw_minutes,lineup_tape

def history():
    out=[]
    for day in range(1,11):
        out.append({'id':'synthetic-'+str(day),'at':f'2024-01-{day:02d}T00:00:00Z','teams':{'old':{'players':{str(p):{'starter':p<5,'stats':{'minutes':float((30 if p<5 else 10)+day%3)}} for p in range(10)}}}})
    return out

class RotationTests(unittest.TestCase):
    cutoff='2024-02-01T00:00:00Z'
    def priors(self):return MinutesPrior().fit(history(),'2024-01-15T00:00:00Z').project({str(i):{'name':'synthetic','teamId':'new'} for i in range(12)},history(),self.cutoff)
    def fact(self,status,**kwargs):return {'status':status,'source':'https://official.example.test','sourceVersion':'synthetic','publishedAt':'2024-01-31T00:00:00Z',**kwargs}
    def test_future_fit_or_history_rejected(self):
        with self.assertRaises(ValueError):MinutesPrior().fit(history(),'2024-01-05T00:00:00Z')
        m=MinutesPrior().fit(history(),'2024-01-15T00:00:00Z')
        with self.assertRaises(ValueError):m.project({'0':{}},history(),'2024-01-06T00:00:00Z')
    def test_traded_identity_and_sparse_roster_players_get_separate_priors(self):
        p=self.priors();self.assertEqual(p['0']['previousTeams'],['old']);self.assertEqual(p['0']['teamId'],'new');self.assertEqual(p['11']['historyGames'],0);self.assertGreater(p['11']['sd'],0)
    def test_unknown_availability_needs_explicit_unweighted_scenario(self):
        with self.assertRaises(ValueError):draw_minutes(self.priors(),{}, {},n=32)
    def test_exact_budgets_caps_and_reproducibility_with_full_roster(self):
        p=self.priors();d={i:True for i in p};a=draw_minutes(p,{},d,n=64);b=draw_minutes(p,{},d,n=64)
        np.testing.assert_array_equal(a['draws'],b['draws']);self.assertTrue(np.all(a['draws'].sum(axis=1)==240));self.assertIsNone(a['scenarioWeights']);self.assertEqual(a['completedBasketballGames'],0)
    def test_confirmed_out_and_sourced_restriction(self):
        p=self.priors();facts={'0':self.fact('out'),'1':self.fact('restricted',maxMinutes=12)};r=draw_minutes(p,facts,{i:True for i in p},n=32)
        self.assertTrue(np.all(r['draws'][:,r['players'].index('0')]==0));self.assertLessEqual(r['draws'][:,r['players'].index('1')].max(),12)
        with self.assertRaises(ValueError):draw_minutes(p,{'0':{'status':'out'}},{i:True for i in p},n=32)
        for invalid in (-1,float('nan'),True):
            with self.assertRaises(ValueError):draw_minutes(p,{'0':self.fact('restricted',maxMinutes=invalid)},{i:True for i in p},n=32)
    def test_future_injury_and_insufficient_capacity_withheld(self):
        p=self.priors();facts={'0':self.fact('out',publishedAt=self.cutoff)}
        with self.assertRaises(ValueError):draw_minutes(p,facts,{i:True for i in p},n=32)
        with self.assertRaises(ValueError):draw_minutes(p,{}, {i:int(i)<4 for i in p},n=32)
    def test_lineups_reconcile_individual_minutes_without_duplicate_players(self):
        p=self.priors();r=draw_minutes(p,{}, {i:True for i in p},n=32);tape=lineup_tape(r['players'],r['draws'][0],substitution_steps=[1,3,5]);spent={i:0. for i in p}
        for row in tape:
            self.assertEqual(len(set(row['players'])),5)
            for pid in row['players']:spent[pid]+=row['endMinute']-row['startMinute']
        np.testing.assert_array_equal([spent[i] for i in r['players']],r['draws'][0])
    def test_overtime_separate_25_team_minutes(self):
        p=self.priors();r=draw_minutes(p,{}, {i:True for i in p},n=32,duration=5.);self.assertTrue(np.all(r['draws'].sum(axis=1)==25));self.assertLessEqual(r['draws'].max(),5)
    def test_hurdle_mass_is_historical_nonparticipation_not_health(self):
        h=history()
        for g in h:
            g['teams']['old']['players']['9']['stats']['minutes']=0.
        p=MinutesPrior().fit(h,'2024-01-15T00:00:00Z').project({str(i):{} for i in range(10)},h,self.cutoff)
        self.assertGreater(p['9']['zeroMinuteProbability'],p['0']['zeroMinuteProbability']);self.assertEqual(p['9']['availability'],'unknown')
        a=draw_minutes(p,{}, {i:True for i in p},n=64,hurdle=True)
        self.assertTrue(np.all(a['draws'].sum(axis=1)==240));self.assertFalse(a['availabilityProbabilitiesInvented'])

if __name__=='__main__':unittest.main()
