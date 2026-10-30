import {describe,expect,it} from 'vitest';
import {combineScenarios} from '../lib/jobs';
type Row=Record<string,any>;
const histogram=(value:number,n=1000)=>({mean:value,median:value,interval90:[value,value],histogram:[{value,count:n}]});
const contract=(id:string,p:number)=>({id,probability:p,pushProbability:0,settlement:{id,kind:'total',threshold:40.5,direction:'over',equality:'no'}});
function run(p:number,seed:number):Row{return {home:'H',away:'A',modelVersion:'SYNTHETIC-MIXTURE-QA',inputDataVersion:'test-hash',eventStart:'2026-12-01T00:00:00Z',evidenceCutoff:'2026-10-01T00:00:00Z',simulations:1000,seed,homeWinProbability:p,awayWinProbability:1-p,tieProbability:0,monteCarloInterval95:[Math.max(0,p-.02),Math.min(1,p+.02)],scoreDistributions:{H:histogram(20),A:histogram(10)},totalDistribution:histogram(30),marginDistribution:histogram(10),players:{},gameEnvironment:{plays:100,drives:20},contracts:[contract('c',p)],jointOutcomes:[{outcomes:['yes'],count:p*1000},{outcomes:['no'],count:(1-p)*1000}],uncertainty:{modelInterval:null},convergence:[]};}

describe('Complete-game availability scenario mixtures',()=>{
 it('centers finite-run intervals on the mixture, aggregates environments and preserves joint evidence',()=>{
  const a=run(.2,1),b=run(.8,2);b.gameEnvironment.plays=150;
  const mixed=combineScenarios([a,b],[.25,.75]);
  expect(mixed.homeWinProbability).toBeCloseTo(.65);
  expect(mixed.monteCarloInterval95[0]).toBeLessThan(.65);
  expect(mixed.monteCarloInterval95[1]).toBeGreaterThan(.65);
  expect(mixed.monteCarloInterval95[0]).toBeGreaterThan(.6);
  expect(mixed.monteCarloSE).toBeCloseTo(Math.sqrt((.25**2*.2*.8+.75**2*.8*.2)/1000));
  expect(mixed.gameEnvironment.plays).toBeCloseTo(137.5);
  expect(mixed.contracts[0].probability).toBeCloseTo(.65);
  expect(mixed.jointOutcomes.find((r:Row)=>r.outcomes[0]==='yes').count/mixed.simulations).toBeCloseTo(.65);
  expect(mixed.uncertainty.modelInterval).toBeNull();expect(mixed.uncertainty.scenarioWeightInterval).toBeNull();
  expect(mixed.seed).toBeNull();expect(mixed.injuryMixture.scenarioSeeds).toEqual([1,2]);
  expect(mixed.evidence.scenarios).toHaveLength(2);
 });
 it('includes players unique to later scenarios and explicitly assigns no-participation zeros',()=>{
  const a=run(.2,1),b=run(.8,2);a.players={first:{receivingYards:histogram(20)}};b.players={backup:{receivingYards:histogram(40)}};
  const mixed=combineScenarios([a,b],[.25,.75]);
  expect(mixed.players.first.receivingYards.mean).toBeCloseTo(5);
  expect(mixed.players.backup.receivingYards.mean).toBeCloseTo(30);
  expect(mixed.players.backup.receivingYards.histogram).toEqual([{value:0,count:500},{value:40,count:1500}]);
  expect(mixed.injuryMixture.absentPlayerZeroPolicy).toMatch(/no participation/);
  expect(mixed.injuryMixture.absentPlayers).toEqual(expect.arrayContaining(['first:scenario1','backup:scenario0']));
 });
 it('withholds independent-stratum SE for missing/reused seeds and uses a dependence-robust numerical interval',()=>{
  const a=run(.2,1),b=run(.8,1);const mixed=combineScenarios([a,b],[.25,.75]);
  expect(mixed.injuryMixture.distinctStreams).toBe(false);expect(mixed.monteCarloSE).toBeNull();
  expect(mixed.monteCarloSEUpperBound).toBeGreaterThan(0);
  expect(mixed.monteCarloInterval95[0]).toBeLessThan(mixed.homeWinProbability);
  expect(mixed.uncertainty.monteCarlo).toMatch(/independence is unverified/);
 });
 it('does not claim numerical certainty when every generated outcome misses or hits',()=>{
  const zero=combineScenarios([run(0,1),run(0,2)],[.4,.6]);
  expect(zero.monteCarloInterval95[0]).toBe(0);expect(zero.monteCarloInterval95[1]).toBeGreaterThan(0);
  const one=combineScenarios([run(1,1),run(1,2)],[.4,.6]);
  expect(one.monteCarloInterval95[0]).toBeLessThan(1);expect(one.monteCarloInterval95[1]).toBe(1);
 });
 it.each([[NaN,NaN],[-.1,1.1],[.2,.2],[Infinity,0]])('rejects invalid weights %s',(...weights)=>{
  expect(()=>combineScenarios([run(.2,1),run(.8,2)],weights)).toThrow(/weight/);
 });
 it('rejects changed settlement/player/team identity and corrupt completed-game counts',()=>{
  const a=run(.2,1),b=run(.8,2);b.contracts[0].settlement.threshold=45.5;
  expect(()=>combineScenarios([a,b],[.5,.5])).toThrow(/settlement/);
  b.contracts[0].settlement=a.contracts[0].settlement;b.home='OTHER';
  expect(()=>combineScenarios([a,b],[.5,.5])).toThrow(/participants/);
  b.home='H';b.totalDistribution.histogram[0].count=999;
  expect(()=>combineScenarios([a,b],[.5,.5])).toThrow(/reconcile/);
 });
 it('aligns joint outcomes by exact contract ID when scenario output order differs',()=>{
  const a=run(.2,1),b=run(.8,2);
  a.contracts=[contract('x',.2),contract('y',.4)];a.jointOutcomes=[{outcomes:['yes','yes'],count:200},{outcomes:['no','yes'],count:200},{outcomes:['no','no'],count:600}];
  b.contracts=[contract('y',.7),contract('x',.8)];b.jointOutcomes=[{outcomes:['yes','yes'],count:700},{outcomes:['no','yes'],count:100},{outcomes:['no','no'],count:200}];
  const mixed=combineScenarios([a,b],[.25,.75]);
  expect(mixed.contracts.map((c:Row)=>c.id)).toEqual(['x','y']);
  expect(mixed.contracts[0].probability).toBeCloseTo(.65);expect(mixed.contracts[1].probability).toBeCloseTo(.625);
  expect(mixed.jointOutcomes.find((r:Row)=>r.outcomes.join(',')==='yes,no').count/mixed.simulations).toBeCloseTo(.075);
 });
 it('does not mutate inputs and rejects incomplete statistics for a present player',()=>{
  const a=run(.2,1),b=run(.8,2),before=JSON.stringify([a,b]);
  const mixed=combineScenarios([a,b],[.25,.75]);mixed.contracts[0].settlement.threshold=99;
  expect(JSON.stringify([a,b])).toBe(before);
  a.players={p:{receivingYards:histogram(20)}};b.players={p:{receptions:histogram(1)}};
  expect(()=>combineScenarios([a,b],[.25,.75])).toThrow(/missing statistic/);
 });
 it('does not assume absent unknown environment metrics are zero',()=>{
  const a=run(.2,1),b=run(.8,2);a.gameEnvironment.pressureRate=.2;a.gameEnvironment.sacks=4;
  const mixed=combineScenarios([a,b],[.25,.75]);
  expect(mixed.gameEnvironment.pressureRate).toBeUndefined();expect(mixed.injuryMixture.unavailableEnvironmentKeys).toContain('pressureRate');
  expect(mixed.gameEnvironment.sacks).toBe(1);
 });
});
