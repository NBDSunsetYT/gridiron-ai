"""Semantics-preserving feature preparation for registered game IDs only.

All history still enters lag construction. Unselected games skip row emission,
not history. Request-local pure-function caches avoid repeated date parsing and
team aggregation; they cannot retain stale evidence across research runs.
"""
import ast,inspect
from functools import lru_cache
from types import FunctionType,SimpleNamespace
from .. import stat_data
from . import data

def records(games,sport,selected_ids):
    source=ast.parse(inspect.getsource(stat_data.records));loops=[n for n in ast.walk(source) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='g' and isinstance(n.iter,ast.Name) and n.iter.id=='games']
    if len(loops)!=1:raise ValueError('Frozen feature-loop structure changed; validate adapter before use')
    guard=ast.parse("if g['id'] not in selected_ids:\n for t in g['teams']:history[t].append(g)\n continue").body[0];loops[0].body.insert(0,guard);ast.fix_missing_locations(source)
    cached_aware=lru_cache(maxsize=20000)(data.aware);namespace={**stat_data.records.__globals__,'selected_ids':frozenset(selected_ids),'aware':cached_aware}
    exec(compile(source,'<registered-history-feature-filter>','exec'),namespace);filtered=namespace['records']
    aggregate={};misses={}
    def total(g,t,s):
        key=(id(g),t,s)
        if key not in aggregate:aggregate[key]=data.total(g,t,s)
        return aggregate[key]
    def game_misses(g):
        key=id(g)
        if key not in misses:misses[key]=data.game_misses(g)
        return misses[key]
    shim=SimpleNamespace(records=filtered,NBA_STATS=stat_data.NBA_STATS,FOOT_STATS=stat_data.FOOT_STATS)
    function=FunctionType(data.records.__code__,{**data.records.__globals__,'stat_data':shim,'aware':cached_aware,'total':total,'game_misses':game_misses})
    return function(games,sport)
