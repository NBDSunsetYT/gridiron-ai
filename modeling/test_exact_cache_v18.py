"""Exact-law cache regressions; no synthetic results are accuracy evidence."""
import unittest
import numpy as np
from .exact_cache_v18 import exact_scalar_cache
from .football_v15 import Predictor,simulate_football,fit_football
from .test_engines_v15 import fixture


class ExactPredictionCache(unittest.TestCase):
    def test_model_identity_and_return_copy_and_restoration(self):
        class Scalar:
            def __init__(self,value):self.value=value
            def predict(self,x,o,d,p=None):return np.array([[self.value+float(x.sum())]])
        original=Scalar.predict;a=Scalar(1);b=Scalar(2);x=np.ones((1,2));o=np.array(['A']);d=np.array(['B'])
        with exact_scalar_cache(Scalar,2) as stats:
            first=a.predict(x,o,d);first[0,0]=999;self.assertEqual(a.predict(x,o,d)[0,0],3);self.assertEqual(b.predict(x,o,d)[0,0],4);self.assertEqual(stats['hits'],1)
            a.predict(x,o,d,np.array(['p']));self.assertEqual(stats['misses'],3)
        self.assertIs(Scalar.predict,original)
    def test_full_seeded_game_statistics_are_identical(self):
        model=fit_football(fixture('CFB'),'CFB','2024-02-01T00:00:00Z','SYNTHETIC');args=(model,'cfb:fixture:0','cfb:fixture:1','2024-02-02T00:00:00Z',1000,18018)
        original=simulate_football(*args,representative_games=0)
        with exact_scalar_cache(Predictor):cached=simulate_football(*args,representative_games=0)
        self.assertEqual({k:v for k,v in cached.items() if k!='createdAt'},{k:v for k,v in original.items() if k!='createdAt'})
    def test_exception_restores_original_method(self):
        original=Predictor.predict
        with self.assertRaises(RuntimeError):
            with exact_scalar_cache(Predictor):raise RuntimeError('SYNTHETIC')
        self.assertIs(Predictor.predict,original)


if __name__=='__main__':unittest.main()
