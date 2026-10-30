import {describe,expect,it} from 'vitest';
import {simulationParlay} from '../lib/simulation-parlay';
const correlated={simulations:100,contracts:[{id:'a',probability:.5},{id:'b',probability:.5}],jointOutcomes:[{outcomes:['yes','yes'],count:50},{outcomes:['no','no'],count:50}]};
describe('Same-game simulation dependence',()=>{
 it('preserves shared outcomes instead of silently multiplying marginals',()=>{const r=simulationParlay(correlated,['a','b']);expect(r.jointProbability).toBe(.5);expect(r.independenceProbability).toBe(.25);expect(r.expectedValue).toBeNull();expect(r.monteCarloInterval95![0]).toBeLessThan(.5);});
 it('uses only an explicitly supplied combined price for value',()=>{const r=simulationParlay(correlated,['a','b'],{odds:200,source:'Verified unit test fixture, not a live quote',sportsbook:'DraftKings',quotedAt:'2026-01-01T00:00:00Z'});expect(r.decimalPayout).toBe(3);expect(r.expectedValue).toBe(.5);});
 it('refuses price-based EV when push repricing rules are unmodeled',()=>{const r=simulationParlay({...correlated,jointOutcomes:[{outcomes:['yes','yes'],count:40},{outcomes:['push','yes'],count:10},{outcomes:['no','no'],count:50}]},['a','b'],{odds:200,source:'Test fixture',sportsbook:'DraftKings',quotedAt:'2026-01-01T00:00:00Z'});expect(r.pushProbability).toBe(.1);expect(r.expectedValue).toBeNull();});
 it('retains fractional scenario weights without claiming a pooled binomial interval',()=>{const r=simulationParlay({...correlated,jointOutcomes:[{outcomes:['yes','yes'],count:42.5},{outcomes:['no','no'],count:57.5}]},['a','b']);expect(r.jointProbability).toBe(.425);expect(r.monteCarloInterval95).toBeNull();});
 it('rejects duplicate selections and nonreconciling or missing joint evidence',()=>{expect(()=>simulationParlay(correlated,['a','a'])).toThrow(/distinct/);expect(()=>simulationParlay(correlated,['a','missing'])).toThrow(/not evaluated/);expect(()=>simulationParlay({...correlated,simulations:101},['a','b'])).toThrow(/reconcile/);});
});
