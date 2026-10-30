import {beforeAll,afterAll,afterEach,describe,it,expect,vi} from 'vitest';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomUUID} from 'node:crypto';
const directory=mkdtempSync(join(tmpdir(),'gridiron-jobs-tests-'));process.env.DATA_DIR=directory;
let db:typeof import('../lib/db'),contracts:typeof import('../lib/contracts'),injuries:typeof import('../lib/injuries'),jobs:typeof import('../lib/jobs');
beforeAll(async()=>{db=await import('../lib/db');contracts=await import('../lib/contracts');injuries=await import('../lib/injuries');jobs=await import('../lib/jobs');});
afterEach(()=>{vi.useRealTimers();vi.unstubAllEnvs();vi.unstubAllGlobals();});afterAll(()=>{db.closeDb();rmSync(directory,{recursive:true,force:true});});
const distribution=(value:number)=>({mean:value,median:value,interval90:[value,value],histogram:[{value,count:1000}]});
function result(contractId:string,eventStart:string,p:number){return{home:'H',away:'A',modelVersion:'TEST-FIXTURE',inputDataVersion:'test-hash',provenance:'TEST FIXTURE ONLY',evidenceCutoff:'2026-09-01T00:00:00Z',eventStart,simulations:1000,homeWinProbability:p,awayWinProbability:1-p,tieProbability:0,totalDistribution:distribution(40),marginDistribution:distribution(7),scoreDistributions:{H:distribution(24),A:distribution(17)},players:{},contracts:[{id:contractId,probability:p,pushProbability:0,conditionalNonPushProbability:p,settlement:{id:contractId,kind:'player',playerId:'fixture-player',stat:'receivingYards',threshold:64.5,direction:'over',equality:'no'}}],jointOutcomes:[{outcomes:['yes'],count:p*1000},{outcomes:['no'],count:(1-p)*1000}],uncertainty:{modelInterval:null},convergence:[]};}
function fixture(){
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-01T12:00:00Z'));vi.stubEnv('SIMULATION_SERVICE_URL','https://quant.test/');vi.stubEnv('SIMULATION_SERVICE_TOKEN','TEST-FIXTURE-TOKEN-32-CHARACTERS-ONLY');
  const userId=randomUUID(),originJob=randomUUID(),now=new Date().toISOString();db.getDb().prepare('INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)').run(userId,userId+'@example.test','fixture',now);
  const injury={entityKey:'fixture-player',player:'TEST FIXTURE player',team:'TEST',status:'questionable',publicationAt:'2026-10-01T11:00:00Z',checkedAt:now,sourceUrl:'https://www.nfl.com/injuries',sourceName:'TEST FIXTURE official report',verified:true,note:'Fixture uncertain designation'};injuries.saveInjury(userId,injury);
  const q=contracts.saveQuote(userId,{contractId:randomUUID(),eventId:'fixture-event',event:'TEST FIXTURE matchup',question:'TEST FIXTURE over 64.5?',threshold:64.5,operator:'gt',settlementDefinition:{kind:'player',home:'H',away:'A',playerId:'fixture-player',stat:'receivingYards',threshold:64.5,direction:'over',equality:'no'},eventStart:'2026-10-02T12:00:00Z',settlementRule:'Official statistic strictly greater than64.5.',rulesUrl:'https://example.test/rules',yesAskCents:'60',noAskCents:'42',quotedAt:now,sourceUrl:'https://example.test/contract',verified:true,entryFeeCents:'1',winFeeCents:'0',feeSource:'TEST FIXTURE only'});
  const first=result(q.contractId,q.eventStart,.6),input={action:'simulate',model:{testFixture:true},home:'H',away:'A',eventStart:q.eventStart,simulations:1000,contracts:[first.contracts[0].settlement]};
  db.getDb().prepare('INSERT INTO simulation_jobs(id,user_id,kind,status,data,result,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)').run(originJob,userId,'simulate','completed','{}',JSON.stringify(first),now,now);
  db.getDb().prepare('INSERT INTO simulation_inputs(id,user_id,job_id,data,created_at) VALUES(?,?,?,?,?)').run(randomUUID(),userId,originJob,JSON.stringify(input),now);
  const p=contracts.savePrediction(userId,{quoteId:q.id,probability:.99,side:'YES',quantity:1,asOf:now,inputsHash:'test-fixture-hash',injuryEntityKeys:['fixture-player'],evidence:{source:'TEST FIXTURE',method:'Mocked signed-service result attachment test',sampleSize:1000,simulationId:originJob}});
  return{userId,q,p,injury};
}
describe('injury-driven durable resimulation',()=>{
  it('uses reproducible distinct scenario seeds and stores the weighted completed result',async()=>{
    const f=fixture();vi.setSystemTime(new Date('2026-10-01T12:00:01Z'));
    injuries.saveInjury(f.userId,{...f.injury,checkedAt:new Date().toISOString(),note:'TEST FIXTURE availability cohort',cohorts:{active:12,limited:4,out:4,sourceUrl:'https://example.test/cohort',description:'SYNTHETIC TEST ONLY comparable availability cohort',asOf:new Date().toISOString()}});
    const seeds:number[]=[];
    vi.stubGlobal('fetch',vi.fn(async(_url:unknown,init:any)=>{const input=JSON.parse(init.body);seeds.push(input.seed);const probability=input.scenario.status==='active'?.8:input.scenario.status==='limited'?.5:.2;return Response.json({...result(f.q.contractId,f.q.eventStart,probability),seed:input.seed});}));
    const processed=await jobs.processSimulationJobs(f.userId);
    expect(processed.jobs[0].status).toBe('completed');expect(seeds).toHaveLength(3);expect(new Set(seeds).size).toBe(3);
    expect(seeds.every(seed=>Number.isSafeInteger(seed)&&seed>=0&&seed<2**48)).toBe(true);
    const record=db.getDb().prepare('SELECT result FROM simulation_jobs WHERE id=?').get(processed.jobs[0].id) as {result:string};const mixed=JSON.parse(record.result);
    expect(mixed.seed).toBeNull();expect(mixed.injuryMixture.scenarioSeeds).toEqual(seeds);expect(mixed.injuryMixture.distinctStreams).toBe(true);
    expect(mixed.homeWinProbability).toBeCloseTo(.62);expect(mixed.contracts[0].probability).toBeCloseTo(.62);expect(mixed.monteCarloSE).toBeGreaterThan(0);
    expect(contracts.contractHistory(f.userId).predictions[0].yesProbability).toBeCloseTo(.62);
  });
  it('uses actual completed probabilities and appends new forecasts after automatic replay',async()=>{
    const f=fixture();expect(f.p.yesProbability).toBe(.6);expect(f.p.sourceValidation).toBe('calculated_from_completed_simulation');
    vi.setSystemTime(new Date('2026-10-01T12:00:01Z'));
    injuries.saveInjury(f.userId,{...f.injury,status:'out',checkedAt:new Date().toISOString(),note:'TEST FIXTURE confirmed out'});
    const transport=vi.fn(async(_url:unknown,init:any)=>{const input=JSON.parse(init.body);expect(input.scenario).toEqual({playerId:'fixture-player',status:'inactive'});return Response.json(result(f.q.contractId,f.q.eventStart,.2));});vi.stubGlobal('fetch',transport);
    const processed=await jobs.processSimulationJobs(f.userId);
    expect(processed.jobs[0].status).toBe('completed');expect(transport).toHaveBeenCalledTimes(1);
    const predictions=contracts.contractHistory(f.userId).predictions;
    expect(predictions).toHaveLength(2);expect(predictions[0].yesProbability).toBe(.2);expect(predictions[0].supersedesPredictionId).toBe(f.p.id);expect(predictions[1].yesProbability).toBe(.6);
    expect(predictions[0].sourceValidation).toBe('calculated_from_completed_simulation');
  });
  it('blocks unsupported empirical scenarios and keeps prior outputs intact',async()=>{
    const f=fixture();vi.setSystemTime(new Date('2026-10-01T12:00:01Z'));injuries.saveInjury(f.userId,{...f.injury,status:'out',checkedAt:new Date().toISOString(),note:'TEST FIXTURE out'});
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(Response.json({detail:'Insufficient scenario evidence: at least four historical games required'},{status:422})));
    const out=await jobs.processSimulationJobs(f.userId);expect(out.jobs[0].status).toBe('blocked');expect(out.jobs[0].reason).toMatch(/Insufficient/);expect(contracts.contractHistory(f.userId).predictions).toHaveLength(1);
  });
  it('requires documented cohorts for uncertain weights and preserves same-run joint dependence in mixtures',()=>{
    expect(jobs.injuryScenarios({status:'questionable'})).toBeNull();expect(jobs.injuryScenarios({status:'out'})).toEqual([{status:'inactive',weight:1}]);
    const a=result('fixture-contract','2026-10-02T12:00:00Z',.8),b=result('fixture-contract','2026-10-02T12:00:00Z',.2);
    const mixture=jobs.combineScenarios([a,b],[.6,.4]);expect(mixture.contracts[0].probability).toBeCloseTo(.56);expect(mixture.jointOutcomes.find((r:any)=>r.outcomes[0]==='yes').count/mixture.simulations).toBeCloseTo(.56);expect(mixture.uncertainty.modelInterval).toBeNull();expect(mixture.uncertainty.method).toBe('stratified_scenario_mixture');
  });
});
