"""Audit-only memoization of immutable, scalar overtime predictors.

No RNG operations, approximation, rounding, fitted-parameter changes, or caches
across predictor instances. Regulation's vectorized fast path is untouched.
Returned copies protect cached values from a caller's in-place modifications.
Never install this process-local adapter in a concurrent web service.
"""
from collections import OrderedDict
from contextlib import contextmanager
from weakref import WeakKeyDictionary

VERSION='exact-scalar-prediction-cache-18.0.0'


@contextmanager
def exact_scalar_cache(predictor_class, maximum_entries=8192):
    if not 1<=maximum_entries<=8192:raise ValueError('Bounded per-predictor cache required')
    original=predictor_class.predict;caches=WeakKeyDictionary();stats={'hits':0,'misses':0}
    def predict(self,x,offense,defense,participant=None):
        if x.shape[0]!=1:return original(self,x,offense,defense,participant)
        key=(x.shape,x.dtype.str,x.tobytes(),tuple(offense),tuple(defense),None if participant is None else tuple(participant))
        cache=caches.setdefault(self,OrderedDict())
        if key in cache:
            stats['hits']+=1;cache.move_to_end(key);return cache[key].copy()
        value=original(self,x,offense,defense,participant);stats['misses']+=1;cache[key]=value.copy()
        if len(cache)>maximum_entries:cache.popitem(last=False)
        return value
    predictor_class.predict=predict
    try:yield stats
    finally:predictor_class.predict=original;caches.clear()
