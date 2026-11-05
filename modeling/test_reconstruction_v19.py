"""Synthetic mechanics/security tests, never accuracy evidence."""
import copy,unittest,tempfile,os
from unittest.mock import patch
import numpy as np
from .reconstruction_v19.evidence import Evidence,reconstruct,scenario_weights
from .reconstruction_v19.registry import Registry,BoundedLoop,SLOTS,promotion_reasons
from .reconstruction_v19.football import mean_preserving_grid
from scipy.special import expit

class EvidenceTests(unittest.TestCase):
    def fact(self,**kw):return Evidence(**{'sport':'CFB','kind':'availability','source':'https://example.edu/official-report','source_sha256':'a'*64,'retrieved_at':'2026-11-05T00:00:00Z','confidence':'official_confirmed','value':{'status':'questionable'},'published_at':'2025-11-01T12:00:00Z','team_id':'cfb:1','player_id':'cfb:p',**kw})
    def test_future_revision_rejects_old_publication(self):
        e=self.fact(modified_at='2025-11-01T20:00:00Z');self.assertEqual(e.for_prediction('CFB','g',['cfb:1'],'2025-11-01T17:00:00Z')[1],'published_or_revised_after_cutoff')
    def test_retrieval_does_not_supply_missing_publication(self):
        e=self.fact(confidence='unverified_timestamp',published_at=None);self.assertFalse(e.for_prediction('CFB','g',['cfb:1'],'2025-11-01T17:00:00Z')[0])
    def test_cross_sport_or_event_join_rejected(self):
        e=self.fact(event_id='g');self.assertFalse(e.for_prediction('NFL','g',['cfb:1'],'2025-11-01T17:00:00Z')[0]);self.assertFalse(e.for_prediction('CFB','other',['cfb:1'],'2025-11-01T17:00:00Z')[0])
    def test_missing_is_not_healthy_or_complete(self):
        c=reconstruct([],'CFB','g',['a','b'],'2025-11-01T17:00:00Z');self.assertFalse(c['injuriesComplete']);self.assertFalse(c['missingAvailabilityMeansHealthy']);self.assertTrue(all(v['status']=='missing' for v in c['coverage'].values()))
    def test_uncertain_availability_has_no_invented_weights(self):
        w=scenario_weights([self.fact()],'CFB','g',['cfb:1'],'2025-11-01T17:00:00Z');self.assertIsNone(w['cfb:p']['weights']);self.assertEqual(len(w['cfb:p']['scenarios']),3)
    def test_explicit_out_deterministic_inactive(self):
        w=scenario_weights([self.fact(value={'status':'out'})],'CFB','g',['cfb:1'],'2025-11-01T17:00:00Z');self.assertEqual(w['cfb:p']['weights']['inactive'],1)
    def test_timezone_and_future_retrieval_checks(self):
        with self.assertRaises(ValueError):self.fact(published_at='2025-11-01')
        with self.assertRaises(ValueError):self.fact(published_at='2027-11-01T12:00:00Z')
    def test_retrieval_does_not_change_semantic_fact_id(self):self.assertEqual(self.fact().id,self.fact(retrieved_at='2026-11-05T01:00:00Z').id)

class RegistryTests(unittest.TestCase):
    gate={'minGames':200,'minWindows':3,'minVerifiedAvailabilityCoverage':.9,'maxBrierRegression':0,'maxLogLossRegression':0,'maxImportantCategoryRegression':.03}
    def passing(self):return {'games':300,'windows':3,'pointInTimeAvailabilityCoverage':1,'outcomesVerified':True,'dataQualityFailures':[],'tunedOnFinalTest':False,'primaryDeltaCI':[-.2,-.01],'moneylineBrierDelta':-.01,'moneylineLogLossDelta':-.01,'importantCategoryMaxRegression':0,'allWindowsNonRegressing':True}
    def test_six_slots_and_no_implicit_validation(self):
        with tempfile.TemporaryDirectory() as p:
            r=Registry(p);self.assertEqual(len(r.state()),6);self.assertFalse(any(v['validated'] for v in r.state().values()))
    def test_player_improvement_cannot_hide_moneyline_regression(self):
        d=self.passing();d['moneylineBrierDelta']=.001;self.assertIn('moneyline_brier_regression',promotion_reasons(d,self.gate))
    def test_research_evaluation_never_promotes(self):
        with tempfile.TemporaryDirectory() as p:
            r=Registry(p);e=r.evaluate('NFL:player','SYNTHETIC',self.passing(),self.gate,'reference_v15');self.assertEqual(e['kind'],'reject');self.assertEqual(r.state()['NFL:player']['model'],'reference_v15')
    def test_cas_and_append_only_rollback(self):
        with tempfile.TemporaryDirectory() as p:
            r=Registry(p);one=r.evaluate('CFB:moneyline','SYNTHETIC-1',self.passing(),self.gate,'reference_v15',True)
            with self.assertRaises(ValueError):r.evaluate('CFB:moneyline','SYNTHETIC-2',self.passing(),self.gate,'reference_v15',True)
            r.evaluate('CFB:moneyline','SYNTHETIC-2',self.passing(),self.gate,'SYNTHETIC-1',True);r.rollback('CFB:moneyline','SYNTHETIC-1','SYNTHETIC-2');self.assertEqual(r.state()['CFB:moneyline']['model'],'SYNTHETIC-1');self.assertEqual(r.events()[0],one);self.assertEqual(r.state()['NFL:moneyline']['model'],'reference_v15')
    def test_bounded_plateau_budget_and_missing_data(self):
        b=BoundedLoop(10);b.record('CFB:player','a',False);b.record('CFB:player','b',False);self.assertEqual(b.next('CFB:player',1)[1],'slot_validation_plateau');self.assertEqual(b.next('NFL:player',11)[1],'compute_budget_exhausted');self.assertEqual(b.next('NFL:player',1,False)[1],'point_in_time_data_limitation')

class StructuralMechanics(unittest.TestCase):
    def test_latent_efficiency_preserves_marginal_completion_mean(self):
        p,a=mean_preserving_grid(.8);nodes,weights=np.polynomial.hermite.hermgauss(16);m=(expit(a[:,None]+.8*np.sqrt(2)*nodes)*weights).sum(axis=1)/np.sqrt(np.pi);np.testing.assert_allclose(m,p,atol=1e-8)
    def test_candidates_cannot_execute_on_vercel(self):
        from .reconstruction_v19.runtime import local_only
        with patch.dict(os.environ,{'VERCEL':'1'}):
            with self.assertRaises(RuntimeError):local_only()
    def test_both_leagues_fit_and_conserve_shared_outcomes(self):
        from .test_engines_v15 import fixture
        from .football_v15 import fit_football
        from .reconstruction_v19.football_fit import enrich
        from .reconstruction_v19.football import simulate_football
        for sport in ['NFL','CFB']:
            rows=fixture(sport);m=enrich(fit_football(rows,sport,'2024-02-01T00:00:00Z','SYNTHETIC'),rows,'team_eb_frailty');prefix='cfb:fixture:' if sport=='CFB' else 'fixture:';f=simulate_football(m,prefix+'0',prefix+'1','2024-02-02T00:00:00Z',1000,19,representative_games=0);self.assertTrue(f['quality']['allGamesAccountingReconciled']);self.assertEqual(f['sport'],sport);self.assertEqual(sum(v['count'] for v in f['totalDistribution']['histogram']),1000);self.assertIsNone(f['calibratedProbability'])


class BasketballReconstruction(unittest.TestCase):
    def test_recency_eb_priors_and_complete_basketball_accounting(self):
        from datetime import datetime,timezone,timedelta
        from .structural_v18.nba import fit_nba
        from .reconstruction_v19.nba_fit import enrich
        from .reconstruction_v19.nba import simulate_nba
        games={}
        for day in range(16):
            for pair in range(5):
                gid=f'SYNTHETIC:{day}:{pair}';date=(datetime(2024,1,1,tzinfo=timezone.utc)+timedelta(days=day)).isoformat();teams={};players=[]
                for side in range(2):
                    tid=str(2*pair+side);roster=[]
                    for i in range(8):
                        made=3+i%3;three=1+i%2;free=1+day%2;p={'athlete_id':int(tid)*10+i,'athlete_display_name':'SYNTHETIC '+tid+' '+str(i),'team_id':tid,'minutes':30.,'starter':i<5,'field_goals_made':made,'field_goals_attempted':10+i%2,'three_point_field_goals_made':three,'three_point_field_goals_attempted':4,'free_throws_made':free,'free_throws_attempted':2,'offensive_rebounds':1,'defensive_rebounds':3,'assists':3,'steals':1,'blocks':1,'turnovers':2,'fouls':3,'points':2*made+three+free};roster.append(p)
                    players.extend(roster);t={k:sum(p[k] for p in roster) for k in roster[0] if isinstance(roster[0][k],(float,int)) and k not in ('athlete_id','starter')};t.update(team_score=t['points'],team_home_away='home' if side==0 else 'away',opponent_team_id=str(2*pair+1-side));teams[tid]=t
                games[gid]={'id':gid,'sport':'NBA','at':date,'teams':teams,'players':players,'freeThrowTrips':{t:[2]*8 for t in teams},'stints':[60,120,180]}
        m=fit_nba(games,'2024-02-01T00:00:00Z','SYNTHETIC','rotation_bootstrap');m['projectedMinutes']={t:{str(p['athlete_id']):30. for p in games['SYNTHETIC:15:0']['players'] if p['team_id']==t} for t in ['0','1']};m=enrich(m,games,'2024-02-01T00:00:00Z');f=simulate_nba(m,'0','1','2024-02-02T00:00:00Z',1000,19)
        self.assertTrue(m['usageEvidence']['priorAndRecentGamesDisjoint']);self.assertTrue(f['quality']['minutesReconciled']);self.assertTrue(f['quality']['playerTeamPointsReconciled']);self.assertTrue(f['quality']['combinedStatsShareOutcomes']);self.assertTrue(all(v>0 for v in m['usageEvidence']['gammaPoissonPriorMinutes'].values()));self.assertIsNone(f['calibratedProbability'])



class DataRepairTests(unittest.TestCase):
    def test_missing_touchdown_stat_is_not_zero(self):
        from .reconstruction_v19.stat_support import supported_value,UnsupportedStatistic
        with self.assertRaises(UnsupportedStatistic):supported_value({'stats':{'passingYards':200}},'passingTouchdowns')
        self.assertEqual(supported_value({'stats':{'passingTouchdowns':0}},'passingTouchdowns'),0)
    def test_schedule_final_qb_weather_and_prices_cannot_leak(self):
        from .reconstruction_v19.stat_support import safe_schedule_metadata
        row={'game_id':'g','away_qb_id':'FINAL','away_coach':'FINAL','temp':32,'wind':10,'away_moneyline':-110};self.assertEqual(safe_schedule_metadata(row),{'game_id':'g'})
    def test_ncaa_and_nfl_clock_statistical_owners_differ(self):
        from .reconstruction_v19.stat_rules import clock_stop_owner
        for kind in ['kneel','spike']:
            self.assertEqual(clock_stop_owner('CFB',kind,'qb','a'),'team-stat:a');self.assertEqual(clock_stop_owner('NFL',kind,'qb','a'),'qb')
    def test_accounting_patch_preserves_nfl_and_game_outcomes(self):
        from .test_engines_v15 import fixture
        from .football_v15 import fit_football
        from .reconstruction_v19.football_fit import enrich
        from .reconstruction_v19 import football,football_rules
        from .iterative_learning import digest
        for sport in ['NFL','CFB']:
            rows=fixture(sport);m=enrich(fit_football(rows,sport,'2024-02-01T00:00:00Z','SYNTHETIC'),rows);prefix='cfb:fixture:' if sport=='CFB' else 'fixture:';args=(prefix+'0',prefix+'1','2024-02-02T00:00:00Z',1000,19);a=football.simulate_football(m,*args,representative_games=0);fixed=copy.deepcopy(m);fixed['version']=football_rules.VERSION;fixed['sha256']=digest({k:v for k,v in fixed.items() if k!='sha256'});b=football_rules.simulate_football(fixed,*args,representative_games=0)
            self.assertEqual(a['scoreDistributions'],b['scoreDistributions']);self.assertEqual(a['marginDistribution'],b['marginDistribution'])
            if sport=='NFL':self.assertEqual(a['players'],b['players'])
            for team,dist in b['teamDistributions'].items():
                roles=b['participantAssumptions'][team];pool={roles['quarterback'],*roles['receivers'],*roles['runners']};adjust=b['teamStatisticAdjustments'].get(team,{}).get('rushingYards',{}).get('mean',0);self.assertAlmostEqual(dist['rushingYards']['mean'],sum(b['players'][p]['rushingYards']['mean'] for p in pool)+adjust)

if __name__=='__main__':unittest.main()
