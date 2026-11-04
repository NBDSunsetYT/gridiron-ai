"""SYNTHETIC invariants. Accuracy evidence is in the immutable local protocol."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from .structural_v18.data import features_for
from .structural_v18.models import Projection,cluster_delta
from .structural_v18.nba import fit_nba,_rotation

class StructuralTests(unittest.TestCase):
    def history(self):
        from .structural_v18.data import BASKETBALL
        games=[]
        for day in range(1,6):
            teams={}
            for t,opp in [('a','b'),('b','a')]:
                players={str(i):{'stats':{s:float(20+i) for s in BASKETBALL},'starter':i<5} for i in range(6) if i!=5 or day!=5}
                totals={s:sum(p['stats'][s] for p in players.values()) for s in BASKETBALL};totals.update(score=100.,plays=95.,dropbacks=0.)
                teams[t]={'players':players,'totals':totals,'opponent':opp}
            games.append({'id':str(day),'at':f'2025-01-0{day}T00:00:00+00:00','end':f'2025-01-0{day}T00:00:00+00:00','season':2025,'teams':teams,'home':'a','away':'b'})
        return games
    def test_features_never_inspect_current_outcome_or_lineup(self):
        history=self.history();event={'id':'new','at':'2025-01-08T00:00:00+00:00','season':2025,'home':'a','away':'b'};h={'a':history,'b':history}
        a=features_for(event,'a',h,'NBA');event['teams']={'a':{'players':{'oracle':999}}};b=features_for(event,'a',h,'NBA')
        self.assertEqual(a,b);self.assertNotIn('oracle',{r['player'] for r in a});self.assertTrue(all(r['featureCutoff']<r['at'] for r in a))
    def test_missing_past_appearance_is_zero_not_dropped(self):
        h=self.history();event={'id':'new','at':'2025-01-08T00:00:00+00:00','season':2025,'home':'a','away':'b'}
        r=next(r for r in features_for(event,'a',{'a':h,'b':h},'NBA') if r['player']=='5' and r['stat']=='minutes')
        self.assertEqual(r['baseline'],20.);self.assertEqual(r['injuryStatus'],'unknown')
    def test_embargo_excludes_same_day_history(self):
        h=self.history();event={'id':'new','at':'2025-01-05T01:00:00+00:00','season':2025,'home':'a','away':'b'}
        rows=features_for(event,'a',{'a':h,'b':h},'NBA');self.assertTrue(all(r['featureCutoff'].startswith('2025-01-04') for r in rows))
    def test_regression_prediction_ignores_future_labels(self):
        rng=np.random.default_rng(18);rows=[{'x':[float(v),float(v*v)],'y':float(v*2+1),'stat':'minutes','featureNames':['a','b'],'baseline':float(v),'player':str(i%5),'team':str(i%2)} for i,v in enumerate(rng.uniform(0,1,200))]
        for f in ['ridge','hierarchical','boosted']:
            m=Projection(f).fit(rows);a=m.predict(rows[:5]);different=copy.deepcopy(rows[:5])
            for r in different:r['y']=1000000;r['opportunity']=1000000
            np.testing.assert_array_equal(a,m.predict(different))
    def test_bootstrap_clusters_games_not_player_rows(self):
        rows=[{'gameId':g,'y':0.} for g in ['a']*100+['b']];r=cluster_delta(rows,[1.]*101,[0.]*101)
        self.assertEqual(r['gameCount'],2);self.assertEqual(r['meanGameMAEDelta'],-1.)
    def test_pbp_gap_does_not_remove_complete_box_rotation(self):
        roster=[{'athlete_id':i,'athlete_display_name':str(i),'team_id':'a','minutes':40.,'starter':i<5,'points':10} for i in range(6)]
        game={'id':'x','at':'2025-01-01T00:00:00+00:00','teams':{'a':{'team_score':60}},'players':roster}
        base={'teams':{'a':[]},'players':{},'playerNames':{}}
        with patch('modeling.structural_v18.nba.base.fit_nba',return_value=base):m=fit_nba({'x':game},'2025-01-02T00:00:00Z','synthetic')
        self.assertEqual(len(m['rotationTeams']['a']),1);self.assertEqual(len(m['players']),6);self.assertEqual(m['teams']['a'],[])
    def test_learned_minutes_reconcile_without_final_roster(self):
        history=[{'at':f'2025-01-0{i}T00:00:00+00:00','roster':[{'athlete_id':p,'minutes':40.,'starter':p<5} for p in range(6)]} for i in range(1,5)]
        m={'rotationTeams':{'a':history},'variant':'learned_minutes','projectedMinutes':{'a':{str(p):20.+p for p in range(6)}}}
        r=_rotation(m,'a',None,'2025-01-08T00:00:00Z');self.assertAlmostEqual(sum(r['minutes'].values()),240);self.assertTrue(all(v<=48 for v in r['minutes'].values()));self.assertFalse(r['verified'])
    def test_unsupported_minute_projection_fails_closed(self):
        history=[{'at':f'2025-01-0{i}T00:00:00+00:00','roster':[{'athlete_id':p,'minutes':40.,'starter':p<5} for p in range(6)]} for i in range(1,5)]
        m={'rotationTeams':{'a':history},'variant':'learned_minutes'}
        with self.assertRaisesRegex(ValueError,'Locked pregame'):_rotation(m,'a',None,'2025-01-08T00:00:00Z')


class JointRotationTests(unittest.TestCase):
    def test_joint_workload_sampling_has_variance_and_reconciles(self):
        from .structural_v18.nba import rotation_budgets
        rosters=[]
        for i in range(5):
            ids=list(range(6)) if i%2==0 else list(range(1,7))
            rosters.append({'at':str(i),'roster':[{'athlete_id':p,'minutes':40.} for p in ids]})
        model={'variant':'rotation_bootstrap','rotationTeams':{'a':rosters}};r={'minutes':{str(p):240/7 for p in range(7)}}
        a=rotation_budgets(model,'a',r,200,np.random.default_rng(18));b=rotation_budgets(model,'a',r,200,np.random.default_rng(18))
        np.testing.assert_array_equal(a,b);np.testing.assert_allclose(a.sum(axis=1),240,atol=1e-6);self.assertTrue((a<=48).all());self.assertGreater(a[:,0].std(),0);self.assertTrue((a[:,0]==0).any())
    def test_fixed_budget_variants_do_not_consume_extra_rng_draws(self):
        from .structural_v18.nba import rotation_budgets
        rng=np.random.default_rng(18);control=np.random.default_rng(18)
        a=rotation_budgets({'variant':'learned_minutes'},'a',{'minutes':{str(p):40. for p in range(6)}},20,rng)
        self.assertEqual(a.shape,(20,6));self.assertEqual(rng.random(),control.random())

class FootballOpportunityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from .test_engines_v15 import fixture
        from .football_v15 import fit_football
        cls.model=fit_football(fixture(),'NFL','2024-02-01T00:00:00Z','synthetic-opportunity-accounting')
    def make_candidate(self):
        from . import football_v15 as ref
        from .structural_v18 import football as candidate
        m=copy.deepcopy(self.model);m['version']=candidate.VERSION;m['projectedOpportunities']={};m['dropbackLogitShift']={t:0. for t in ['fixture:0','fixture:1']}
        for t in m['dropbackLogitShift']:
            r=ref.participant_roles(self.model,t,None,'2024-02-02T00:00:00Z');p=m['projectedOpportunities'][t]={}
            for role,stat in [('receivers','targets'),('runners','carries')]:
                for pid,v in r[role].items():p.setdefault(pid,{})[stat]=v
            p[r['quarterback']]={'passingAttempts':40.}
        return m
    def test_zero_shift_preserves_conditional_distribution(self):
        from .structural_v18.football import _shift_play,KINDS
        p=np.array([[.5,.4,.1],[.2,.3,.5]]);m={'dropbackLogitShift':{'a':0.,'b':0.}}
        np.testing.assert_allclose(_shift_play(p.copy(),[KINDS.index('pass'),KINDS.index('rush'),KINDS.index('punt')],np.array([0,1]),['a','b'],m),p,rtol=1e-14)
    def test_learned_complete_games_reconcile_shared_stats(self):
        from .structural_v18.football import simulate_football
        m=self.make_candidate();f=simulate_football(m,'fixture:0','fixture:1','2024-02-02T00:00:00Z',1000,18018,representative_games=0)
        self.assertTrue(f['quality']['allGamesAccountingReconciled']);self.assertIsNone(f['calibratedProbability'])
        self.assertAlmostEqual(sum(v['passingYards']['mean'] for v in f['players'].values()),sum(v['receivingYards']['mean'] for v in f['players'].values()))
        for d in f['scoreDistributions'].values():self.assertEqual(sum(b['count'] for b in d['histogram']),1000)
    def test_known_inactive_is_not_reselected_by_regression(self):
        from .structural_v18.football import participant_roles
        m=self.make_candidate();m['projectedOpportunities']['fixture:0']['fixture:0:qb1']={'passingAttempts':100.}
        r=participant_roles(m,'fixture:0',{'inactive':['fixture:0:qb1']},'2024-02-02T00:00:00Z');self.assertNotEqual(r['quarterback'],'fixture:0:qb1')


if __name__=='__main__':unittest.main()
