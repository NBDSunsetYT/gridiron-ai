"""SYNTHETIC mechanics; real held-out NFL/CFB audits are separate reports."""
import copy,unittest
from datetime import datetime,timedelta,timezone
from .test_simulator import fixture_csv
from .fit import fit_csv
from .gafie import fit_gafie,simulate_gafie,GafieNFL
from .simulator import simulate,Evidence

class GafieTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=fit_csv(fixture_csv(),'SYNTHETIC MECHANICAL FIXTURE ONLY','2024-02-01T00:00:00Z')['model'];rows=[]
        for block in range(3):
            for row in base['rows']:
                item=copy.deepcopy(row);item['game']=row['game']+'-'+str(block);item['at']=(datetime.fromisoformat(row['at'])+timedelta(days=block*7)).isoformat();rows.append(item)
        cls.model={**base,'rows':rows};cls.artifact=fit_gafie(cls.model);cls.model['gafie']=cls.artifact
    def test_chronological_training_and_json_coefficients(self):
        a=self.artifact;self.assertFalse(a['productionEligible']);self.assertFalse(set(a['trainingGames'])&set(a['holdoutGames']));self.assertTrue(a['validation']['chronological']);self.assertGreater(a['validation']['candidate']['n'],0);self.assertEqual(len(a['coefficients'][0]),len(a['features']))
    def test_default_engine_remains_numerically_identical(self):
        args=(self.model,'SYNTH-A','SYNTH-B',100,14,'2024-03-01T00:00:00Z');stock=simulate(*args);injected=simulate(*args,_evidence_factory=Evidence)
        for key in ['players','scoreDistributions','totalDistribution','marginDistribution','correlations']:self.assertEqual(stock[key],injected[key])
    def test_candidate_runs_complete_consistent_shared_games(self):
        r=simulate_gafie(self.model,'SYNTH-A','SYNTH-B',200,14,'2024-03-01T00:00:00Z');self.assertEqual(r['simulations'],200);self.assertEqual(r['modelStatus'],'experimental_unpromoted');self.assertIn('gafie-',r['modelVersion'])
        for distribution in r['scoreDistributions'].values():self.assertEqual(sum(b['count'] for b in distribution['histogram']),200)
        game=r['representativeGames'][0];players=game['players'].values();self.assertEqual(sum(p.get('completions',0) for p in players),sum(p.get('receptions',0) for p in players));self.assertEqual(sum(p.get('passingYards',0) for p in players),sum(p.get('receivingYards',0) for p in players));self.assertGreater(len(game['plays']),20)
        again=simulate_gafie(self.model,'SYNTH-A','SYNTH-B',200,14,'2024-03-01T00:00:00Z');self.assertEqual(r['players'],again['players']);self.assertEqual(r['scoreDistributions'],again['scoreDistributions'])
    def test_exact_artifact_identity_is_required(self):
        bad=copy.deepcopy(self.model);bad['gafie']['inputVersion']='WRONG';self.assertRaisesRegex(ValueError,'exact-input',GafieNFL,bad,'SYNTH-A','SYNTH-B')
        bad=copy.deepcopy(self.model);bad['gafie']['coefficients'][0][0]=float('nan');self.assertRaisesRegex(ValueError,'numerical',GafieNFL,bad,'SYNTH-A','SYNTH-B')

if __name__=='__main__':unittest.main()
