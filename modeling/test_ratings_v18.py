"""Synthetic mechanism tests; never a market or predictive-accuracy claim."""
import copy,unittest
from datetime import datetime,timedelta,timezone
import numpy as np
from .ratings import fit_ratings,fit_offsets,attach,matchup,Context,validate,RATED_VERSION,sha
from .football_v15 import fit_football,simulate_football
from .test_engines_v15 import fixture

def epa_fixture():
    rows=[];teams=['A','B','C','D'];rng=np.random.default_rng(1818)
    for day in range(24):
        for i,o in enumerate(teams):
            d=teams[(i+1+day%3)%4]
            if d==o:continue
            at=(datetime(2024,1,1,tzinfo=timezone.utc)+timedelta(days=day)).isoformat()
            for j in range(8):rows.append({'sport':'NFL','season':2024,'game':str(day)+'-'+o,'o':o,'d':d,'home':int(i%2==0),'at':at,'eventAt':at,'epa':(.6 if o=='A' else -.3 if o=='B' else 0)-(.5 if d=='C' else -.4 if d=='D' else 0)+rng.normal(0,.1),'restDifference':float(day%3-1),'sourceVersion':'SYNTHETIC','availableAt':at})
    return rows

class RatingsResearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rows=epa_fixture();cls.ratings=fit_ratings(cls.rows,'NFL',2024,'2024-02-01T00:00:00Z')
    def test_blocked_fits_are_strictly_before_validation_and_event(self):
        for f in self.ratings['blockedCV']['folds']:self.assertLess(f['trainLastAt'],f['validationFirstEventAt'])
        bad=copy.deepcopy(self.rows);bad[0]['at']='2024-02-01T00:00:00Z'
        with self.assertRaises(ValueError):fit_ratings(bad,'NFL',2024,'2024-02-01T00:00:00Z')
        with self.assertRaises(ValueError):fit_ratings(self.rows,'CFB',2024,'2024-02-01T00:00:00Z')
    def test_opponent_changes_supported_epa_distribution_materially(self):
        strong,_=matchup(self.ratings,'A','C','2024-02-02T00:00:00Z',variant='ridge');weak,_=matchup(self.ratings,'A','D','2024-02-02T00:00:00Z',variant='ridge')
        self.assertGreater(strong['C']['defense']-weak['D']['defense'],.15)
    def test_bayesian_point_sd_and_regression_are_fitted(self):
        m=self.ratings;self.assertGreaterEqual(m['weekly']['processVariance'],0);self.assertTrue(0<=m['weekly']['regressionToMean']<=1);p,_=matchup(m,'A','B','2024-02-02T00:00:00Z');self.assertTrue(all(p[t][k+'SD']>=0 for t in p for k in ['offense','defense']));self.assertIsNotNone(m['restCoefficient'])
    def test_checksum_season_and_cutoff_are_not_bypassed(self):
        bad=copy.deepcopy(self.ratings);bad['leagueMeanEPA']+=1
        with self.assertRaises(ValueError):validate(bad)
        with self.assertRaises(ValueError):matchup(self.ratings,'A','B','2025-10-02T00:00:00Z')
        with self.assertRaises(ValueError):matchup(self.ratings,'A','B',self.ratings['fittingCutoff'])
    def test_more_monte_carlo_draws_do_not_shrink_parameter_sd(self):
        ctx=Context(self.ratings,['A','B'],'2024-02-02T00:00:00Z');before=copy.deepcopy(ctx.values);ctx.draw(np.random.default_rng(18),10000);ctx.draw(np.random.default_rng(19),50000);self.assertEqual(ctx.values,before)
    def test_new_artifact_migration_and_shared_game_accounting(self):
        rows=fixture();base=fit_football(rows,'NFL','2024-02-01T00:00:00Z','SYNTHETIC')
        epa=[{'sport':'NFL','season':2024,'game':r['game'],'o':r['o'],'d':r['d'],'home':r['home'],'at':r['at'],'eventAt':r['at'][:10]+'T00:00:00+00:00','epa':r['yards']/10,'sourceVersion':'SYNTHETIC'} for r in rows if r['kind'] in ('pass','rush','sack')]
        rating=fit_ratings(epa,'NFL',2024,'2024-02-01T00:00:00Z');rated=attach(base,fit_offsets(rows,base,rating));self.assertEqual(rated['version'],RATED_VERSION);self.assertNotIn('ratings',base)
        result=simulate_football(rated,'fixture:0','fixture:1','2024-02-02T00:00:00Z',1000,1819,representative_games=0);self.assertTrue(result['quality']['allGamesAccountingReconciled']);self.assertEqual(result['modelVersion'],RATED_VERSION);self.assertIsNone(result['calibratedProbability']);self.assertIn('posterior',result['ratings'])
    def test_untrained_or_wrong_base_offsets_are_rejected(self):
        base=fit_football(fixture(),'NFL','2024-02-01T00:00:00Z','SYNTHETIC')
        with self.assertRaises(ValueError):attach(base,self.ratings)
    def test_empty_source_eligibility_preserves_schema_and_withholds_all_rows(self):
        import pyarrow as pa
        from .ratings import filter_source_table
        empty=pa.table({'event':pa.array([],type=pa.string()),'epa':pa.array([],type=pa.float64())});self.assertEqual(filter_source_table(empty,[]).schema,empty.schema)
        table=pa.table({'event':['prior','future'],'epa':[1.,999.]});self.assertEqual(filter_source_table(table,[True,False]).to_pylist(),[{'event':'prior','epa':1.}])
        with self.assertRaises(ValueError):filter_source_table(table,[])


if __name__=='__main__':unittest.main()
