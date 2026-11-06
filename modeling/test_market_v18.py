"""Stage-one regression fixtures are synthetic and never accuracy evidence."""
import copy,json,random,unittest,tempfile
from pathlib import Path
import numpy as np
from .test_simulator import fixture_csv
from .test_engines_v15 import fixture
from .fit import fit_csv
from .simulator import Evidence,is_late
from .football_transitions_v18 import fit_transitions,two_point_probability,starts,migrate
from .football_v15 import fit_football,simulate_football,participant_roles,VERSION

class PoolRepairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=fit_csv(fixture_csv(),'SYNTHETIC','2024-02-01T00:00:00Z')['model']
    def test_current_opponent_keys_and_source_provenance(self):
        m=copy.deepcopy(self.model)
        for r in m['rows']:
            if r['o']=='SYNTH-A':r['d']='SYNTH-C'
        e=Evidence(m,'SYNTH-A','SYNTH-B');self.assertTrue(any(k[:2]==('SYNTH-A','SYNTH-B') for k in e.pools));self.assertFalse(any(k[:2]==('SYNTH-A','SYNTH-C') for k in e.pools))
        p=e.sample(random.Random(5),'SYNTH-A','SYNTH-B',1,75,10,0,600);self.assertEqual(p['d'],'SYNTH-B')
        self.assertTrue(p['qb'].startswith('SYNTH-A'))
    def test_league_prior_is_final_backoff_and_owns_participants(self):
        e=Evidence(self.model,'SYNTH-A','SYNTH-B');e.pools={k:v for k,v in e.pools.items() if k[0]=='league'};e.sample_pools={}
        for seed in range(30):
            p=e.sample(random.Random(seed),'SYNTH-A','SYNTH-B',1,75,10,0,600);self.assertEqual(p['o'],'SYNTH-A');self.assertEqual(p['d'],'SYNTH-B');self.assertTrue(p['receiver'].startswith('SYNTH-A'))
        self.assertIn(4,e.backoff)
    def test_dirichlet_mixture_uses_sample_count_not_half_probability(self):
        e=Evidence(self.model,'SYNTH-A','SYNTH-B');row=next(r for r in e.rows if r['kind']=='pass');other=next(r for r in e.rows if r['kind']=='rush');key=('SYNTH-A','SYNTH-B',1,2,2,0,False);e.prior_strength=20;e.sample_pools[key]=(0,[row]*4,[other]*40);rng=random.Random(18);fraction=sum(e.sample(rng,'SYNTH-A','SYNTH-B',1,75,10,0,600)['kind']=='pass' for _ in range(5000))/5000;self.assertAlmostEqual(fraction,4/24,delta=.02)
    def test_temporal_observation_guard(self):
        m=copy.deepcopy(self.model);m['rows'][0]['at']=m['asOf']
        with self.assertRaises(ValueError):Evidence(m,'SYNTH-A','SYNTH-B')
    def test_one_late_definition_handles_both_halves(self):
        self.assertTrue(is_late(120));self.assertFalse(is_late(121));self.assertTrue(is_late(1900,True));self.assertFalse(is_late(1921,True));self.assertFalse(is_late(1800,True));self.assertTrue(is_late(0,True));np.testing.assert_array_equal(is_late(np.array([119,121])),[True,False])
    def test_spike_and_incomplete_oob_have_no_extra_runoff(self):
        e=Evidence(self.model,'SYNTH-A','SYNTH-B');p={'kind':'spike','elapsed':40,'liveSeconds':2,'complete':0};self.assertEqual(e.clock_charge(random.Random(1),p,50,-3,2),2)
        p.update(kind='pass',complete=0,outOfBounds=True);self.assertEqual(e.clock_charge(random.Random(1),p,50,-3,2),2)
        p['complete']=1;self.assertEqual(e.clock_charge(random.Random(1),p,250,0,2),2);self.assertEqual(e.clock_charge(random.Random(1),p,500,0,2),40)
    def test_tempo_is_estimated_or_unavailable_not_fixed(self):
        m=copy.deepcopy(self.model)
        for r in m['rows']:
            if is_late(r['clock'],True):r.update(script=-3,elapsed=10)
        e=Evidence(m,'SYNTH-A','SYNTH-B');self.assertAlmostEqual(e.tempo_multiplier,1/3);self.assertIsNone(Evidence(self.model,'SYNTH-A','SYNTH-B').tempo_multiplier)

class TransitionRepairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=fit_football(fixture(),'NFL','2024-02-01T00:00:00Z','SYNTHETIC')
    def test_restart_cause_and_unknown_rates(self):
        rows=fixture();external={'cutoff':'2024-02-01T00:00:00+00:00','sourceVersion':'SYNTHETIC','rows':[{'kind':'drive_start','at':'2024-01-01T00:00:00Z','team':'fixture:0','cause':k,'field':v} for k,v in [('kickoff',75),('post_score',70),('post_turnover',35),('post_punt',80)]]};t=fit_transitions(rows,external['cutoff'],external);m={**self.model,'transitions':t}
        self.assertEqual([starts(m,'fixture:0',k) for k in ['kickoff','post_score','post_turnover','post_punt']],[[75],[70],[35],[80]]);self.assertIsNone(t['returnTouchdowns']['interception']['rate'])
    def test_return_touchdown_rates_are_actual_counts(self):
        external={'cutoff':'2024-02-01T00:00:00+00:00','rows':[{'at':'2024-01-01T00:00:00Z','kind':'interception','returnTouchdown':i==0,'returnYards':i} for i in range(10)]};t=fit_transitions(fixture(),external['cutoff'],external);self.assertEqual(t['returnTouchdowns']['interception']['rate'],.1);self.assertIsNone(t['returnTouchdowns']['kickoff']['rate'])
    def test_fitted_contextual_two_point_decision_and_no_lookahead(self):
        external={'cutoff':'2024-02-01T00:00:00+00:00','rows':[{'at':'2024-01-01T00:00:00Z','kind':'two_point' if i%2 else 'extra_point','clock':30 if i%2 else 1300,'script':-2 if i%2 else 14} for i in range(40)]};t=fit_transitions(fixture(),external['cutoff'],external);m={**self.model,'transitions':t};p=two_point_probability(m,np.array([-2,14]),np.array([30,1300]));self.assertGreater(p[0],p[1]);self.assertTrue(t['twoPointDecision']['contextual']);external['rows'][0]['at']=external['cutoff']
        with self.assertRaises(ValueError):fit_transitions(fixture(),external['cutoff'],external)
    def test_legacy_artifact_load_and_explicit_migration(self):
        from . import football_v15_legacy as legacy
        m=legacy.fit_football(fixture(),'NFL','2024-02-01T00:00:00Z','SYNTHETIC');before=copy.deepcopy(m);a=legacy.simulate_football(m,'fixture:0','fixture:1','2024-02-02T00:00:00Z',1000,18,representative_games=0);b=simulate_football(m,'fixture:0','fixture:1','2024-02-02T00:00:00Z',1000,18,representative_games=0);self.assertEqual(a['scoreDistributions'],b['scoreDistributions']);self.assertEqual(a['players'],b['players']);new=migrate(m,fixture());self.assertEqual(new['version'],VERSION);self.assertEqual(new['play'],m['play']);self.assertEqual(m,before)
    def test_participant_caps_respect_explicit_depth_order(self):
        m=copy.deepcopy(self.model)
        for h in m['histories']['fixture:0'].values():h['receiver']={f'wr{i}':8-i for i in range(8)};h['runner']={f'rb{i}':6-i for i in range(6)}
        current={'quarterback':'fixture:0:qb0','verified':True,'source':'https://example.test/synthetic-depth','availableAt':'2024-02-01T00:00:00Z','depthChart':{'receivers':['wr7','wr6'],'runners':['rb5']}}
        r=participant_roles(m,'fixture:0',current,'2024-02-02T00:00:00Z');self.assertEqual(len(r['receivers']),6);self.assertEqual(len(r['runners']),4);self.assertEqual(list(r['receivers'])[:2],['wr7','wr6']);self.assertEqual(list(r['runners'])[0],'rb5')
    def test_two_point_attempts_are_used_and_game_accounting_passes(self):
        m=copy.deepcopy(self.model);m['transitions']['twoPointDecision'].update(coefficients=None,n=1,twoPoint=1);r=simulate_football(m,'fixture:0','fixture:1','2024-02-02T00:00:00Z',1000,18,representative_games=0);self.assertGreater(r['gameEnvironment']['twoPointAttempts'],0);self.assertTrue(r['quality']['allGamesAccountingReconciled'])
    def test_fitted_return_scores_reconcile_team_points(self):
        m=copy.deepcopy(self.model)
        for kind in ('interception','fumble','punt','kickoff'):m['transitions']['returnTouchdowns'][kind].update(n=100,touchdowns=5,rate=.05)
        r=simulate_football(m,'fixture:0','fixture:1','2024-02-02T00:00:00Z',1000,19,representative_games=0);self.assertTrue(r['quality']['allGamesAccountingReconciled'])
    def test_position_prior_is_estimated_and_missing_is_unknown(self):
        from .football_transitions_v18 import position_priors
        rows=fixture()
        for r in rows:
            if r.get('receiver'):r['receiverPosition']='WR'
            if r.get('runner'):r['runnerPosition']='RB'
        prior=position_priors(rows);self.assertIn('WR',prior['byPosition']['targets']);self.assertGreater(prior['byPosition']['targets']['WR']['observations'],1);self.assertTrue(prior['missingPositionIsUnknown'])
    def test_source_cutoff_and_spike_metadata_join(self):
        import pyarrow as pa,pyarrow.parquet as pq
        from .football_source_v18 import transition_evidence,augment_rows
        raw=[{'game_id':'SYNTHETIC','play_id':1,'qtr':1,'time_of_day':'2024-01-01T00:00:00+00:00','posteam':'A','defteam':'B','down':1,'yardline_100':75,'game_seconds_remaining':3500,'score_differential':0,'pass_attempt':True,'qb_spike':True,'out_of_bounds':False,'fixed_drive':1},{'game_id':'SYNTHETIC','play_id':2,'qtr':1,'time_of_day':'2025-01-01T00:00:00+00:00','posteam':'A','defteam':'B','down':2,'yardline_100':75,'game_seconds_remaining':3495,'score_differential':0,'pass_attempt':True,'qb_spike':False,'out_of_bounds':False,'fixed_drive':1}]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'raw.parquet';pq.write_table(pa.Table.from_pylist(raw),p);ev=transition_evidence([p],'NFL','2024-02-01T00:00:00Z');self.assertTrue(all(r['at']<'2024-02-01' for r in ev['rows']));r={'game':'SYNTHETIC','at':raw[0]['time_of_day'],'sport':'NFL','o':'A','d':'B','kind':'pass','down':1,'field':75};new=augment_rows([r],ev);self.assertEqual(new[0]['kind'],'spike');self.assertEqual(r['kind'],'pass')
    def test_legacy_category_indices_remain_unchanged(self):
        from .football_v15 import KINDS
        from .integration_v22.clock import KINDS as CLOCK_KINDS
        self.assertEqual(KINDS,('pass','rush','punt','field_goal','kneel','penalty'));self.assertEqual(CLOCK_KINDS[len(KINDS)],'sack');self.assertEqual(self.model['kindOrder'][-1],'spike')
    def test_partially_unknown_return_flags_do_not_fit_a_biased_zero_rate(self):
        external={'cutoff':'2024-02-01T00:00:00+00:00','rows':[{'at':'2024-01-01T00:00:00Z','kind':'punt','returnTouchdown':v} for v in [True,False,None]]};r=fit_transitions(fixture(),external['cutoff'],external)['returnTouchdowns']['punt'];self.assertIsNone(r['rate']);self.assertEqual(r['unverifiedEvents'],1)
    def test_incomplete_pass_cannot_be_a_fumble(self):
        r=simulate_football(self.model,'fixture:0','fixture:1','2024-02-02T00:00:00Z',1000,27,representative_games=2)
        for p in r['representativePlays']:
            if p['kind']=='pass' and not p['complete']:self.assertFalse(p['fumbleLost'])
    def test_null_position_identity_cannot_attach_to_conversion_rows(self):
        import pyarrow as pa,pyarrow.parquet as pq
        from .football_source_v18 import augment_rows
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'positions.parquet';pq.write_table(pa.Table.from_pylist([{'game_id':'g','player_id':None,'position':'TEAM'}]),path);row={'game':'g','at':'2024-01-01T00:00:00Z','o':'A','kind':'extra_point'};self.assertEqual(augment_rows([row],{'rows':[]},[path]),[row])
    def test_cached_and_uncached_source_reconstruction_are_identical(self):
        import pyarrow as pa,pyarrow.parquet as pq
        from .football_source_v18 import transition_evidence
        rows=[{'game_id':'SYNTHETIC','play_id':1,'qtr':1,'time_of_day':'2024-01-01T00:00:00Z','posteam':'A','defteam':'B','down':1,'yardline_100':75,'pass_attempt':True}]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'raw.parquet';pq.write_table(pa.Table.from_pylist(rows),path);cache={};a=transition_evidence([path],'NFL','2024-02-01T00:00:00Z',cache);b=transition_evidence([path],'NFL','2024-02-01T00:00:00Z',cache);c=transition_evidence([path],'NFL','2024-02-01T00:00:00Z');self.assertEqual(a,b);self.assertEqual(a,c);self.assertEqual(len(cache),1)
    def test_pre_hurdle_artifacts_migrate_without_new_regressions(self):
        from . import football_v15_baseline as baseline
        old=baseline.fit_football(fixture(),'NFL','2024-02-01T00:00:00Z','SYNTHETIC');new=migrate(old,fixture());self.assertNotIn('passTouchdown',new);self.assertEqual(old['play'],new['play']);self.assertFalse(new['migration']['coefficientsRefit']);r=simulate_football(new,'fixture:0','fixture:1','2024-02-02T00:00:00Z',1000,18,representative_games=0);self.assertTrue(r['quality']['allGamesAccountingReconciled'])
    def test_nonfinite_flags_are_unknown_rather_than_true(self):
        from .football_source_v18 import observed_flag
        for v in [None,float('nan'),float('inf'),'unknown',2]:self.assertIsNone(observed_flag(v))
        self.assertIs(observed_flag(0.),False);self.assertIs(observed_flag(1.),True)
    def test_frozen_protection_set_and_strict_cutoff_filter(self):
        from .football_source_v18 import eligible_training
        rows=[{'game':g,'at':'2024-01-01T00:00:00Z'} for g in ['allowed','sealed']];self.assertEqual(eligible_training(rows,'2024-02-01T00:00:00Z',{'sealed'}),rows[:1]);rows.append({'game':'future','at':'2024-02-01T00:00:00Z'})
        with self.assertRaises(ValueError):eligible_training(rows,'2024-02-01T00:00:00Z',set())
    def test_missing_or_postkickoff_prices_cannot_pass_gate_two(self):
        from .market_gates_v18 import spread_gate
        q={'product':'sportsbook','market':'spread','phase':'closing','verified':True,'book':'SYNTHETIC','sourceVersion':'SYNTHETIC','source':'https://example.test/synthetic','homeHandicap':-3};rows=[{'eventId':'synthetic','eventAt':'2024-01-01T00:00:00Z','modelHomeMargin':3.,'market':q}];r=spread_gate(rows);self.assertIsNone(r['spreadCorrelation']);self.assertFalse(r['passed']);self.assertIsNone(r['CLV']);q['capturedAt']='2024-01-02T00:00:00Z';self.assertEqual(spread_gate(rows)['qualifiedGames'],0)
    def test_stages_cannot_skip_failed_previous_gate(self):
        from .market_gates_v18 import require_previous,gate1
        with self.assertRaises(ValueError):require_previous({'1':{'passed':False}},2)
        self.assertFalse(gate1({'tsPassed':795,'pythonPassed':500,'typecheckPassed':True,'allCommandsExitZero':True},{'gamesCompleted':499,'allAccountingReconciled':True,'simulatedCompleteGames':4990000})['passed'])
    def test_parallel_execution_partitions_preserve_protocol_and_game_seeds(self):
        import importlib.util
        path=Path(__file__).resolve().parents[1]/'scripts/market-v18-workers.py';spec=importlib.util.spec_from_file_location('audit_workers_fixture',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        protocol={'selection':[{'gameId':str(i),'sport':sport,'originalSeed':i+18} for i,sport in enumerate(['NFL','CFB','NFL','CFB'])],'code':{'source':'immutable'},'simulationsPerGame':10000};before=copy.deepcopy(protocol)
        partitions=[m.selection_for_sport(protocol,sport) for sport in ('NFL','CFB')];self.assertEqual(protocol,before);self.assertEqual(sorted(r['gameId'] for p in partitions for r in p['selection']),['0','1','2','3']);self.assertTrue(all(p['code']==protocol['code'] and p['simulationsPerGame']==10000 for p in partitions))
        with self.assertRaises(ValueError):m.selection_for_sport(protocol,'NBA')
        duplicate=copy.deepcopy(protocol);duplicate['selection'].append(duplicate['selection'][0])
        with self.assertRaises(ValueError):m.selection_for_sport(duplicate,'NFL')
    def test_regression_report_keeps_regressions_and_missing_markets(self):
        from .market_audit_report_v18 import audit_report
        row={'gameId':'SYNTHETIC','sport':'NFL','baselineVersion':'synthetic','scoreErrors':[3.,-3.],'baselineScoreErrors':[1.,-1.],'brier':.3,'baselineBrier':.2,'logLoss':.8,'baselineLogLoss':.6,'players':[{'id':'synthetic','stat':'passingYards','error':4.,'oldError':2.,'covered90':False}],'simulations':10000,'accountingReconciled':True,'strictPregameQualified':False};r=audit_report([row],['SYNTHETIC']);m=r['leagues']['NFL']['gameMetrics'];self.assertEqual(m['teamScoreMAE']['pairedGameDelta']['difference'],2.);self.assertEqual(m['teamScoreMAE']['pairedGameDelta']['interval95'],[2.,2.]);self.assertIsNone(r['CLV']);self.assertFalse(r['productionPromotion']);self.assertEqual(r['leagues']['NFL']['playerMetrics']['passingYards']['pairedGameBlockMAEDelta95'],[2.,2.])
        with self.assertRaises(ValueError):audit_report([row,row],['SYNTHETIC'])
        with self.assertRaises(ValueError):audit_report([row],['missing'])

if __name__=='__main__':unittest.main()
