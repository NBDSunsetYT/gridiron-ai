"""Software invariants only. Synthetic fixtures are not accuracy evidence."""
import copy,json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
import numpy as np
from .dynamic_v24.completion.data import records,features_only,total
from .dynamic_v24.completion.models import OpportunityPooling,candidate,mixture_samples
from .dynamic_v24.completion.selection import choose,decision,Registry,paired_loss
from .dynamic_v24.completion.joint import bounded_budget,HeadFootballKernel,football_mechanics,nba_rates,nba_mechanics
from .test_fullgame_v23 import GeneratedBasketballTests
from .test_engines_v15 import fixture
from .fullgame_v23.modes import context,Mode
SOURCE={'source':'https://example.test/software-only','sourceVersion':'SYNTHETIC'}
def ctx(s):return context(Mode.MECHANICS,s,'SYNTHETIC-completion',[SOURCE])

def training(n=160):
    rows=[]
    for i in range(n):
        x=[float(i%7),20.,18.,20.,4.,5.,i%2,24.,22.,7.,30.,1.,20.,7.,100.,40.,40.,40.,.5,.5,.1,1.,0.,1.,80.,0.]
        rows.append({'gameId':'SYNTHETIC-'+str(i//2),'at':f'2020-{i//28+1:02d}-{i%28+1:02d}','player':'p'+str(i%2),'team':'H','role':'QB','stat':'passingYards','x':x,'featureNames':['f'+str(j) for j in range(26)],'baseline':140.,'ewma':140.,'priorCount':5,'y':140.+i%5,'opportunity':20.,'opportunityKind':'passingAttempts','actualTeamOpportunity':40.,'actualGameMisses':80.})
    return rows

class SelectionTests(unittest.TestCase):
    def test_complete_manifest_versions_are_idempotent_and_objective_scoped(self):
        w={'games':40,'paired':{'adjustedCI':[-2,-1]},'candidate':{'cdfBrier':.2,'cdfLogLoss':.5,'coverage':{'0.9':.9}},'reference':{'cdfBrier':.2,'cdfLogLoss':.5,'coverage':{'0.9':.9}}};d=decision([w,w],'expected_value');record={'sport':'NFL','stat':'receivingYards','family':'SYNTHETIC','modelVersion':'SYNTHETIC','trainingCutoff':'2023-01-01T00:00:00Z','sourceVersions':{'software-only':'a'*64},'sampleSize':{'games':80,'observations':160},'metrics':[w,w],'uncertainty':[w['paired'],w['paired']],'purpose':'expected_value','estimand':'conditional_mean','decision':d,'modelSHA256':['b'*64],'productionPromotion':False}
        with tempfile.TemporaryDirectory() as tmp:
            reg=Registry(Path(tmp)/'r.json');first=reg.register(record);self.assertEqual(reg.register(record),first);self.assertEqual(len(json.loads(reg.path.read_text())['versions']),1)
            forged=copy.deepcopy(record);forged['decision']['conditionalImprovementEstablished']=False
            with self.assertRaises(ValueError):reg.register(forged)
    def test_joint_probabilities_require_independent_past_windows(self):
        from .dynamic_v24.completion.selection import joint_probability_gate
        model={'sha256':'SYNTHETIC'};match={'cutoff':'2024-01-01T00:00:00Z'};w={'gameIds':['software-'+str(i) for i in range(30)],'end':'2023-01-01T00:00:00Z','brierDeltaCI95':[-.01,.001],'logLossDeltaCI95':[-.01,.001],'coverage90Regression':0,'calibrationAccepted':True};certificate={'jointProbabilityValidation':{'modelHash':'SYNTHETIC','windows':[w,w]}}
        with self.assertRaises(ValueError):joint_probability_gate(model,match,certificate)
        certificate['jointProbabilityValidation']['windows'][1]=w|{'gameIds':['other-'+str(i) for i in range(30)],'end':'2025-01-01T00:00:00Z'}
        with self.assertRaises(ValueError):joint_probability_gate(model,match,certificate)
    def test_mean_selection_cannot_pick_zero_td_median(self):
        inner={'median':{'mae':.1,'rmse':.8,'crps':.5},'mean':{'mae':.3,'rmse':.5,'crps':.2}};kind={'median':'conditional_median','mean':'conditional_mean'}
        self.assertEqual(choose(inner,kind,'expected_value'),'mean');self.assertEqual(choose(inner,kind,'median'),'median');self.assertEqual(choose(inner,kind,'distribution'),'mean')
    def test_research_win_is_not_production_or_joint_permission(self):
        w={'games':40,'paired':{'adjustedCI':[-2,-1]},'candidate':{'cdfBrier':.2,'cdfLogLoss':.5,'coverage':{'0.9':.9}},'reference':{'cdfBrier':.2,'cdfLogLoss':.5,'coverage':{'0.9':.9}}};r=decision([w,w],'expected_value');self.assertTrue(r['conditionalImprovementEstablished']);self.assertFalse(r['jointReplacementAllowed']);self.assertFalse(r['productionPromotionEligible'])
    def test_distribution_rejects_brier_logloss_and_coverage_regression(self):
        w={'games':40,'paired':{'adjustedCI':[-2,-1]},'candidate':{'cdfBrier':.3,'cdfLogLoss':.8,'coverage':{'0.9':.7}},'reference':{'cdfBrier':.2,'cdfLogLoss':.5,'coverage':{'0.9':.9}}};self.assertFalse(decision([w,w],'distribution')['conditionalImprovementEstablished'])
    def test_game_cluster_bootstrap_does_not_count_duplicate_players_as_games(self):
        rows=[{'gameId':str(i),'y':0} for i in range(30)];a=np.ones(30)*2;b=np.ones(30);r=paired_loss(rows,a,b,bootstraps=1000);twice=paired_loss(rows+rows,np.r_[a,a],np.r_[b,b],bootstraps=1000);self.assertEqual(r,twice)
    def test_registry_demands_provenance_and_forbids_direct_joint_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Registry(Path(tmp)/'r.json')
            with self.assertRaises(ValueError):r.register({'family':'bogus'})
            with self.assertRaises(ValueError):r.joint_heads('CFB')
    def test_mixture_keeps_tails_instead_of_averaging_them_to_zero(self):
        d=mixture_samples([np.full((2,1000),-10),np.full((2,1000),10)],[.5,.5]);self.assertEqual(set(np.unique(d)),{-10,10});self.assertGreater(d.var(),90)

class OpportunityTests(unittest.TestCase):
    def test_zero_opportunity_only_player_uses_population_rate(self):
        rows=training();rows[0]=rows[0]|{'player':'known-zero-history','opportunity':0.,'y':0.};m=OpportunityPooling('passingYards').fit(rows);self.assertTrue(np.all(np.isfinite(m.predict(features_only(rows[:2])))))
    def test_shared_opportunity_budget_and_error_factors(self):
        model=OpportunityPooling('passingYards').fit(training());x=features_only(training()[:2]);f=model.factors(x);self.assertLessEqual(f['share'].sum(),1+1e-9);self.assertLessEqual(f['opportunity'].sum(),f['teamVolume'][0]+1e-9);np.testing.assert_allclose(model.predict(x),f['opportunity']*f['efficiency'])
    def test_current_outcome_fields_are_rejected_by_opportunity_predictor(self):
        m=OpportunityPooling('passingYards').fit(training())
        with self.assertRaises(ValueError):m.predict(training()[:2])
    def test_missing_opportunity_and_impossible_team_totals_are_not_filled(self):
        rows=training()
        for r in rows:r['opportunity']=None
        with self.assertRaises(ValueError):OpportunityPooling('passingYards').fit(rows)
        rows=training();rows[0]['opportunity']=50
        with self.assertRaises(ValueError):OpportunityPooling('passingYards').fit(rows)
    def test_rebound_exposure_requires_observed_missed_shots(self):
        rows=training()
        for r in rows:r.update(stat='rebounds',opportunityKind='minutes',actualGameMisses=None)
        with self.assertRaises(ValueError):OpportunityPooling('rebounds',True).fit(rows)
    def test_count_head_never_samples_fractional_attempts(self):
        rows=training()
        for r in rows:r.update(stat='fieldGoalAttempts',y=float(10+int(r['y'])%3))
        m=candidate('negative_binomial','fieldGoalAttempts',rows[:120],rows[120:]);d=m.samples(features_only(rows[:3]),n=100);self.assertTrue(np.all(d>=0));np.testing.assert_array_equal(d,np.rint(d))

class FeatureTests(unittest.TestCase):
    def test_efficient_selection_keeps_all_historical_inputs_exact(self):
        from .dynamic_v24.completion.efficient_data import records as efficient
        gs=[]
        for day in range(16):
            teams={t:{'players':{'p'+t:{'stats':{'minutes':30.,'rebounds':float(day+2)},'starter':day%2==0}},'totals':{'score':100+day},'opponent':'A' if t=='H' else 'H'} for t in ['H','A']};gs.append({'id':'g'+str(day),'sport':'NBA','at':(datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(days=day*3)).isoformat(),'season':2020,'teams':teams,'home':'H','away':'A'})
        ids={'g14','g15'};expected=[r for r in records(gs,'NBA') if r['gameId'] in ids];self.assertEqual(efficient(gs,'NBA',ids),expected)
    def test_unknown_current_lineup_or_changed_final_box_does_not_change_features(self):
        gs=[]
        for day in range(16):
            teams={t:{'players':{'p'+t:{'stats':{'minutes':30.,'rebounds':float(day+2)},'starter':day%2==0}},'totals':{'score':100+day},'opponent':'A' if t=='H' else 'H'} for t in ['H','A']};gs.append({'id':'g'+str(day),'sport':'NBA','at':(datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(days=day*3)).isoformat(),'season':2020,'teams':teams,'home':'H','away':'A'})
        a=[r for r in records(gs,'NBA') if r['gameId']=='g15'];changed=copy.deepcopy(gs);changed[-1]['teams']['H']['players']['pH']['stats']['rebounds']=999;changed[-1]['teams']['H']['players']['pH']['starter']=False;changed[-1]['teams']['H']['totals']['score']=999;b=[r for r in records(changed,'NBA') if r['gameId']=='g15'];self.assertEqual(features_only(a),features_only(b));self.assertNotEqual([r['y'] for r in a],[r['y'] for r in b])
    def test_anonymous_team_attempts_stay_in_team_budget(self):
        g={'teams':{'T':{'players':{'q':{'stats':{'passingAttempts':20}}},'totals':{'passingAttempts':23},'unassignedTeamCredits':{'passingAttempts':3}}}};self.assertEqual(total(g,'T','passingAttempts'),23)

class BankTests(unittest.TestCase):
    def test_two_team_heads_are_not_collapsed_into_one_anonymous_player(self):
        rows=[self.rows[0]|{'player':'__team__','team':t} for t in ['H','A']];r=self.bank.bundle('NFL',rows,'2021-01-01T00:00:00Z',ctx('NFL'));self.assertEqual(set(r['teamEstimates']),{'H','A'});self.assertEqual(r['estimates'],{})
    def test_ambiguous_player_team_mapping_is_rejected(self):
        rows=[self.rows[0]|{'team':t} for t in ['H','A']]
        with self.assertRaises(ValueError):self.bank.bundle('NFL',rows,'2021-01-01T00:00:00Z',ctx('NFL'))
    def setUp(self):
        import pickle,hashlib
        from .dynamic_v24.stat_models import StatModel
        from .dynamic_v24.completion.bank import HeadBank
        from .overnight_v20.state import digest
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.path=self.root/'artifacts/dynamic-v24/software.pickle';self.path.parent.mkdir(parents=True);self.path.write_bytes(pickle.dumps(StatModel('rolling5','receptions').fit(training())));sha=hashlib.sha256(self.path.read_bytes()).hexdigest();entry={'sport':'NFL','stat':'receptions','modelPath':str(self.path.relative_to(self.root)),'modelSHA256':sha,'availableAfter':'2020-01-01T00:00:00Z','modelVersion':'SYNTHETIC','role':'research_reference'};self.manifest={'heads':[entry]};self.manifest['sha256']=digest(self.manifest);self.bank=HeadBank(self.manifest,self.root);self.rows=[{'gameId':'SYNTHETIC-completion','player':'p','stat':'receptions','baseline':3.,'x':training()[0]['x'],'featureLastGame':'2019-01-01T00:00:00Z'}]
    def tearDown(self):self.tmp.cleanup()
    def test_exact_version_is_selected_only_after_its_fit_cutoff(self):
        r=self.bank.bundle('NFL',self.rows,'2021-01-01T00:00:00Z',ctx('NFL'));self.assertEqual(r['estimates']['p']['receptions'],3.);self.assertEqual(self.bank.bundle('NFL',self.rows,'2019-06-01T00:00:00Z',ctx('NFL'))['estimates'],{})
    def test_candidate_cannot_be_selected_before_confirmation_ends(self):
        from .dynamic_v24.completion.bank import HeadBank
        from .overnight_v20.state import digest
        reference=self.manifest['heads'][0]
        old=reference|{'availableAfter':'2022-01-01T00:00:00Z','trainingThrough':'2020-06-01T00:00:00Z','modelVersion':'candidate-old','role':'conditional_research_candidate'}
        recent=old|{'trainingThrough':'2020-12-01T00:00:00Z','modelVersion':'candidate-recent'}
        manifest={'heads':[reference,old,recent]};manifest['sha256']=digest(manifest);bank=HeadBank(manifest,self.root)
        before=bank.bundle('NFL',self.rows,'2021-01-01T00:00:00Z',ctx('NFL'))
        at=bank.bundle('NFL',self.rows,'2022-01-01T00:00:00Z',ctx('NFL'))
        after=bank.bundle('NFL',self.rows,'2023-01-01T00:00:00Z',ctx('NFL'))
        self.assertEqual(before['manifest']['heads'][0]['role'],'research_reference')
        self.assertEqual(at['manifest']['heads'][0]['role'],'research_reference')
        self.assertEqual(after['manifest']['heads'][0]['modelVersion'],'candidate-recent')
    def test_labels_and_duplicate_rows_are_not_accepted(self):
        with self.assertRaises(ValueError):self.bank.bundle('NFL',[self.rows[0]|{'y':100}],'2021-01-01T00:00:00Z',ctx('NFL'))
        with self.assertRaises(ValueError):self.bank.bundle('NFL',self.rows*2,'2021-01-01T00:00:00Z',ctx('NFL'))
    def test_tampered_artifact_or_manifest_and_unqualified_joint_use_fail(self):
        from .dynamic_v24.completion.bank import HeadBank
        self.path.write_bytes(b'SYNTHETIC corrupt artifact')
        with self.assertRaises(ValueError):self.bank.bundle('NFL',self.rows,'2021-01-01T00:00:00Z',ctx('NFL'))
        with self.assertRaises(ValueError):HeadBank(self.manifest|{'heads':[]},self.root)
        with self.assertRaises(ValueError):self.bank.bundle('NFL',self.rows,'2021-01-01T00:00:00Z',ctx('NFL')|{'mode':Mode.FORECAST})

class JointTests(unittest.TestCase):
    def test_nba_accounting_quality_rejects_source_mismatch_without_editing_it(self):
        from .dynamic_v24.completion.nba_quality import audit
        g=GeneratedBasketballTests().game();g['id']='SYNTHETIC';g['teams']['H']['team_score']=g['teams']['A']['team_score']=90
        for p in g['players']:p['points']=15
        for t in g['teams'].values():t.update(three_point_field_goals_made=12,free_throws_made=18)
        self.assertTrue(audit(g)['usable']);bad=copy.deepcopy(g);bad['teams']['H']['field_goals_attempted']+=1;before=copy.deepcopy(bad);self.assertFalse(audit(bad)['usable']);self.assertEqual(bad,before)
    def test_reference_nba_draws_unchanged_and_specialized_twos_exclude_three_attempts(self):
        from .dynamic_v24 import basketball
        from .dynamic_v24.completion.basketball_engine import complete_games
        g=GeneratedBasketballTests().game();a=basketball.mechanics_games(g,ctx('NBA'),2,240244,[4,8,12]);b=complete_games(g,ctx('NBA'),2,240244,[4,8,12]);self.assertEqual(a['results'],b['results'])
        for p in g['players']:
            p['three_point_field_goals_attempted']=p['field_goals_attempted'] if str(p['athlete_id']) in ('1','11') else 0;p['three_point_field_goals_made']=p['field_goals_made'] if str(p['athlete_id']) in ('1','11') else 0
        est={str(p['athlete_id']):{'minutes':40.,'fieldGoalAttempts':float(p['field_goals_attempted']),'threePointAttempts':float(p['three_point_field_goals_attempted'])} for p in g['players']};rates=nba_rates(g,est,{'sport':'NBA','estimand':'conditional_mean','modelVersions':['SYNTHETIC']},ctx('NBA'));r=nba_mechanics(rates,ctx('NBA'),games=3,clock_intervals=[4,8,12])
        for trial in r['results']:
            for pid in ['1','11']:self.assertEqual(trial['players'][pid]['fieldGoalAttempts'],trial['players'][pid]['threePointAttempts'])
    def test_zero_expected_points_do_not_require_impossible_positive_shooting(self):
        game,est=self.nba();est['1']['points']=0.;est['1']['assists']=0.;r=nba_rates(game,est,{'sport':'NBA','estimand':'conditional_mean','modelVersions':['SYNTHETIC']},ctx('NBA'));p=next(p for p in r['players'] if p['athlete_id']==1);self.assertEqual(p['field_goals_made'],0);self.assertEqual(p['free_throws_made'],0)
    def test_signed_yardage_is_valid_but_negative_counts_are_not(self):
        from .dynamic_v24.completion.joint import validate_estimates
        validate_estimates({'p':{'rushingYards':-2.,'carries':1.}})
        with self.assertRaises(ValueError):validate_estimates({'p':{'carries':-1.}})
    def test_capped_minute_budget_is_exact_and_rejects_impossible_roster(self):
        p=bounded_budget([50,45,43,40,38,30,10]);self.assertAlmostEqual(p.sum(),240);self.assertTrue(np.all(p<=48));self.assertTrue(np.all(p>=0))
        with self.assertRaises(ValueError):bounded_budget([48]*4)
    def nba(self):
        game=GeneratedBasketballTests().game();est={str(p['athlete_id']):{'minutes':40.,'points':15.,'rebounds':5.,'assists':3.,'fieldGoalAttempts':10.,'threePointAttempts':4.,'freeThrowAttempts':4.} for p in game['players']};return game,est
    def test_nba_specialized_shots_minutes_and_rebounds_share_actual_events(self):
        game,est=self.nba();r=nba_rates(game,est,{'sport':'NBA','estimand':'conditional_mean','modelVersions':['SYNTHETIC']},ctx('NBA'));self.assertAlmostEqual(sum(p['minutes'] for p in r['players'] if p['team_id']=='H'),240);result=nba_mechanics(r,ctx('NBA'),games=3,clock_intervals=[4,8,12]);self.assertTrue(result['mechanicalInvariantsPassed']);self.assertFalse(result['jointHeadAccuracyValidated'])
        for row in result['results']:
            self.assertEqual(row['reboundableMisses'],row['creditedRebounds'])
            for t in row['team']:self.assertEqual(row['scores'][t],sum(v['points'] for p,v in row['players'].items() if (int(p)<10)==(t=='H')))
    def test_nba_incompatible_shots_and_scoring_fail_closed(self):
        game,est=self.nba();est['1']['threePointAttempts']=100
        with self.assertRaises(ValueError):nba_rates(game,est,{'sport':'NBA','estimand':'conditional_mean','modelVersions':['SYNTHETIC']},ctx('NBA'))
    def football(self,sport):
        rows=fixture(sport);teams=sorted({r['o'] for r in rows})[:2];rows=[r for r in rows if r['o'] in teams]
        for r in rows:r['complete']=int(r['kind']=='pass' and r['complete'] and not r['int']);r['int']=int(r['kind']=='pass' and r['int'])
        owners={p:r['o'] for r in rows for p in [r.get('qb'),r.get('runner'),r.get('receiver')] if p};est={}
        for p in owners:
            if ':qb' in p:est[p]={'passingAttempts':16.,'passingYards':120.}
            elif ':wr' in p:est[p]={'receptions':6.,'receivingYards':80.}
            else:est[p]={'carries':12.,'rushingYards':48.}
        return HeadFootballKernel(sport,teams,rows,owners,estimates=est,head_manifest={'sport':sport,'estimand':'conditional_mean','modelVersions':['SYNTHETIC']})
    def test_both_football_leagues_reconcile_yards_and_clock_with_heads(self):
        for sport in ['NFL','CFB']:
            k=self.football(sport);r=football_mechanics(k,ctx(sport),2024,games=3,conversions={'extra_point':[1,0],'two_point':[0,1]})
            for trial in r['results']:
                self.assertEqual(trial['regulationSeconds'],3600)
                for t,v in trial['team'].items():self.assertEqual(v['passingYards'],v['receivingYards'])
    def test_median_head_and_conditional_context_cannot_enter_joint_adapter(self):
        game,est=self.nba()
        with self.assertRaises(ValueError):nba_rates(game,est,{'sport':'NBA','estimand':'conditional_median','modelVersions':['SYNTHETIC']},ctx('NBA'))
        with self.assertRaises(ValueError):nba_rates(game,est,{'sport':'NBA','estimand':'conditional_mean','modelVersions':['SYNTHETIC']},ctx('NBA')|{'mode':Mode.CONDITIONAL})
    def test_changed_availability_requires_new_scenario_not_automatic_redistribution(self):
        k=self.football('CFB');pid=next(p for p in k.estimates if ':wr' in p);k.unavailable.add(pid)
        with self.assertRaises(ValueError):k.pick(np.random.default_rng(1),k.owners[pid],'receptions')

if __name__=='__main__':unittest.main()
