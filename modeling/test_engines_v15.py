"""SYNTHETIC mechanical fixtures only; never forecast/accuracy evidence."""
import copy
from datetime import datetime,timezone,timedelta
import unittest
import numpy as np
from .football_v15 import fit_football,simulate_football,participant_roles,Predictor,numeric
from .nba_v15 import beta_prior


def fixture(sport='NFL'):
    rng=np.random.default_rng(15);rows=[];prefix='cfb:fixture:' if sport=='CFB' else 'fixture:'
    for day in range(16):
        for side in range(4):
            team=prefix+str(side);defense=prefix+str((side+1)%4);game=f'synthetic:{day}:{side}'
            for i in range(50):
                kind=['pass','rush','pass','rush','sack','punt','field_goal','penalty'][i%8];qb=team+':qb'+str(i%2 if i<8 else 0);receiver=team+':wr'+str(i%3);runner=team+':rb'+str(i%2)
                rows.append({'sport':sport,'game':game,'at':(datetime(2024,1,1,tzinfo=timezone.utc)+timedelta(days=day,seconds=i)).isoformat(),'o':team,'d':defense,'kind':kind,'down':i%4+1,'distance':i%10+1,'field':int(rng.integers(1,99)),'clock':3600-i*50,'script':int(rng.integers(-14,15)),'home':int(side%2==0),'elapsed':int(rng.choice([5,12,25,35,40])),'yards':int(rng.integers(-3,22)) if kind not in ('sack','penalty') else -5,'complete':int(i%3!=0),'int':int(i%17==0),'fumble':0,'qb':qb,'receiver':receiver,'runner':runner,'made':int(i%3!=0),'puntNet':40,'drive':str(i//6),'firstDownPenalty':False})
            for kind in ['extra_point','two_point']:
                rows.append({'sport':sport,'game':game,'at':(datetime(2024,1,1,tzinfo=timezone.utc)+timedelta(days=day,seconds=60)).isoformat(),'o':team,'d':defense,'kind':kind,'made':int(day%3!=0)})
    return rows


class FootballV15Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=fit_football(fixture(),'NFL','2024-02-01T00:00:00Z','synthetic:mechanical-fixture')
    def test_future_and_mixed_league_rejected(self):
        rows=fixture();rows[0]['at']='2025-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'Separate league'):fit_football(rows,'NFL','2024-02-01T00:00:00Z','synthetic')
        with self.assertRaisesRegex(ValueError,'Separate league'):fit_football(fixture('CFB'),'NFL','2024-02-01T00:00:00Z','synthetic')
    def test_factored_identity_predictions_are_numerically_identical(self):
        teams=['fixture:0','fixture:1'];players=['fixture:0:qb0','fixture:1:qb0'];p=Predictor(self.model['dropback']);p.bind(teams,players)
        side=np.array([0,1,0]);part=np.array([0,1,0]);x=numeric([1,3,4],[10,4,1],[75,20,3],[3600,130,12],[-3,7,0],[1,0,1]);off=np.asarray(teams)[side];defense=np.asarray(teams)[1-side]
        np.testing.assert_allclose(p.fast(x,side,part),p.predict(x,off,defense,np.asarray(players)[part]),rtol=1e-13,atol=1e-13)
        np.testing.assert_allclose(p.fast(x,side,part,True),p.probabilities(x,off,defense,np.asarray(players)[part]),rtol=1e-13,atol=1e-13)
    def test_current_qb_replaces_inactive_historical_starter(self):
        lineup={'quarterback':'fixture:0:qb1','inactive':['fixture:0:qb0'],'verified':True,'source':'https://example.com/synthetic-test-lineup','availableAt':'2024-02-01T00:00:00Z'}
        roles=participant_roles(self.model,'fixture:0',lineup,'2024-02-02T00:00:00Z');self.assertEqual(roles['quarterback'],'fixture:0:qb1');self.assertNotIn('fixture:0:qb0',roles['runners'])
        bad={**lineup,'availableAt':'2024-02-03T00:00:00Z'}
        with self.assertRaisesRegex(ValueError,'before kickoff'):participant_roles(self.model,'fixture:0',bad,'2024-02-02T00:00:00Z')
    def test_seed_complete_games_mass_and_shared_accounting(self):
        args=(self.model,'fixture:0','fixture:1','2024-02-02T00:00:00Z')
        a=simulate_football(*args,simulations=1000,seed=15,representative_games=1);b=simulate_football(*args,simulations=1000,seed=15,representative_games=1)
        for key in ['scoreDistributions','players','marginDistribution','convergence','representativePlays']:self.assertEqual(a[key],b[key])
        self.assertTrue(a['quality']['allGamesAccountingReconciled']);self.assertIsNone(a['calibratedProbability']);self.assertFalse(a['quality']['productionEligible'])
        for d in a['scoreDistributions'].values():self.assertEqual(sum(b['count'] for b in d['histogram']),1000)
        self.assertAlmostEqual(sum(p['passingYards']['mean'] for p in a['players'].values()),sum(p['receivingYards']['mean'] for p in a['players'].values()))
    def test_invalid_counts_seeds_and_unverified_qb(self):
        args=(self.model,'fixture:0','fixture:1','2024-02-02T00:00:00Z')
        for count in [True,0,100001]:
            with self.assertRaises(ValueError):simulate_football(*args,simulations=count)
        with self.assertRaisesRegex(ValueError,'nonnegative'):simulate_football(*args,seed=True)
        with self.assertRaisesRegex(ValueError,'no prior'):participant_roles(self.model,'fixture:0',{'quarterback':'unknown'},args[-1])
    def test_cfb_has_separate_fit_and_overtime_without_ties(self):
        m=fit_football(fixture('CFB'),'CFB','2024-02-01T00:00:00Z','synthetic:mechanics')
        r=simulate_football(m,'cfb:fixture:0','cfb:fixture:1','2024-02-02T00:00:00Z',1000,15,representative_games=0)
        self.assertEqual(r['sport'],'CFB');self.assertEqual(r['tieProbability'],0);self.assertTrue(r['quality']['allGamesAccountingReconciled'])


class NBAPriorTests(unittest.TestCase):
    def test_empirical_bayes_uses_observed_attempts_and_shrinks(self):
        a,b=beta_prior([50,25,75,10,30,65],[100]*6);self.assertGreater(a,0);self.assertGreater(b,0)
        prior=a/(a+b);posterior=(a+1)/(a+b+1);self.assertGreater(posterior,prior);self.assertLess(posterior,1)
    def test_impossible_binomial_evidence_rejected(self):
        with self.assertRaises(ValueError):beta_prior([2]*5,[1]*5)


if __name__=='__main__':unittest.main()
