"""Mechanics/equivalence only. Synthetic workloads are not model validation."""
import importlib.util,json,random,sys,unittest,copy,time,os
from pathlib import Path
from unittest.mock import patch
from .test_simulator import fixture_csv
from .fit import fit_csv
from . import simulator
from . import hierarchical_props
from .football_prop_feeds import PropLineClient

def original(name):
    path=Path(__file__).parents[1]/'tests'/'fixtures'/'performance-originals'/(name+'.py')
    spec=importlib.util.spec_from_file_location('modeling._original_'+name,path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m

class PerformanceEquivalence(unittest.TestCase):
    def test_hierarchical_candidate_all_parameters_validation_and_calibration_unchanged(self):
        from .test_hierarchical_props import HierarchicalTests
        records=HierarchicalTests().records();baseline=original('hierarchical_props');baseline.VERSION=hierarchical_props.VERSION
        a=baseline.pool_candidate(records,'receptions','WR',2026);b=hierarchical_props.pool_candidate(records,'receptions','WR',2026)
        self.assertEqual(a,b)
    def test_exact_random_sequence_pools_and_generated_nfl_games(self):
        old=original('simulator');model=fit_csv(fixture_csv(),'SYNTHETIC MECHANICS','2024-02-01T00:00:00Z',100,{'recencyHalfLifeDays':90,'conditionalShrinkage':True})['model']
        a=old.Evidence(model,'SYNTH-A','SYNTH-B');b=simulator.Evidence(model,'SYNTH-A','SYNTH-B');ra=random.Random(1211);rb=random.Random(1211)
        for _ in range(30):self.assertEqual(old.simulate_game(a,ra,['SYNTH-A','SYNTH-B'],trace=True),simulator.simulate_game(b,rb,['SYNTH-A','SYNTH-B'],trace=True))
        self.assertEqual(a.backoff,b.backoff)
    def test_render_page_exactly_matches_full_board_without_mutable_cache_escape(self):
        from .test_football_prop_feeds import FreePropsTests
        fixture=FreePropsTests();fixture.setUp()
        try:
            board=copy.deepcopy(fixture.board);out=board[0]['bookmakers'][0]['markets'][0]['outcomes'];out.extend([{**out[0],'player_id':'espn:'+str(i),'description':'SYNTHETIC '+str(i)} for i in range(2,1002)])
            client=PropLineClient(lambda url,key:(200,{},json.dumps(board).encode()))
            whole=client.read('NFL');page=client.read_page('NFL',500,500)
            self.assertEqual(page['items'],whole['items'][500:1000]);page['items'][0]['player']['name']='MUTATED'
            self.assertNotEqual(client.read_page('NFL',500,500)['items'][0]['player']['name'],'MUTATED')
            self.assertEqual(page['totalResults'],len(whole['items']))
        finally:fixture.tearDown()
