import {beforeEach,afterEach,describe,it,expect,vi} from 'vitest';
const s=vi.hoisted(()=>({jobs:new Map<string,any>(),snapshots:[] as any[],contracts:[] as any[],after:[] as Array<()=>Promise<void>>,writes:[] as any[],detail:{} as any,quota:true}));
vi.mock('next/server',()=>({after:(work:()=>Promise<void>)=>s.after.push(work)}));
vi.mock('../lib/public-nfl/service',()=>({publicGameDetail:vi.fn(async()=>structuredClone(s.detail))}));
vi.mock('../lib/public-nfl/store',()=>({sharedWrite:vi.fn(async(payload:any)=>{s.writes.push(structuredClone(payload));if(payload.action==='job_enqueue')return{id:payload.id,status:'queued'};if(payload.action==='job_claim')return s.quota?{id:payload.id,status:'running'}:null;return{id:payload.id,status:'completed'};})}));
vi.mock('../lib/cloud/store',async original=>{const real:any=await original();return{...real,saveRecord:vi.fn(async(ctx:any,kind:string,data:any)=>{s.jobs.set(data.id,{id:data.id,user_id:ctx.user.id,kind,data:structuredClone(data)});return data;}),records:vi.fn(async(ctx:any,kind:string,options:any)=>[...s.jobs.values()].filter(row=>row.user_id===ctx.user?.id&&row.kind===kind&&(!options.dataKind||row.data.kind===options.dataKind)).slice(0,options.limit).map(row=>structuredClone(row))),record:vi.fn(async(ctx:any,id:string,kind:string)=>{const row=s.jobs.get(id);if(!row||row.user_id!==ctx.user?.id||row.kind!==kind)throw Object.assign(Error('Owned record not found'),{status:404});return structuredClone(row);})};});
import {queuePrivatePropResearch,readPrivatePropResearch,executePrivatePropResearch,listPrivatePropResearch} from '../lib/player-props/private-research';
import {verifyCloudResult} from '../lib/cloud/attestation';
import {decodeCloudData} from '../lib/cloud/codec';
const first='a'.repeat(64),second='b'.repeat(64),now='2026-10-30T21:00:00Z';
function context(owner='SYNTHETIC-OWNER-1'){
 return{user:{id:owner},accessToken:'SYNTHETIC-VERIFIED-JWT',client:{from(table:string){const filters:Array<[string,unknown]>=[];let value:any,ids:string[]|undefined;const query:any={select(){return query;},in(_column:string,input:string[]){ids=input;return query;},eq(column:string,input:unknown){filters.push([column,input]);return query;},update(input:any){value=input;return query;},then(resolve:any,reject:any){return(async()=>{
  if(table==='gridiron_records'){
   const id=filters.find(([key])=>key==='id')?.[1] as string,row=s.jobs.get(id);
   const matches=row&&filters.every(([key,input])=>key.startsWith('data->>')?row.data[key.slice(7)]===input:row[key]===input||key==='id'&&id===input);
   if(matches&&value){row.data=decodeCloudData(structuredClone(value.data));return{data:[{id}],error:null};}
   return{data:[],error:null};
  }
  const rows=table==='shared_prop_snapshots'?s.snapshots:s.contracts;return{data:structuredClone(rows.filter(row=>!ids||ids.includes(row.id))),error:null};
 })().then(resolve,reject);}};return query;}}} as any;
}
function contract(id:string,playerId:string,stat='receivingYards'){
 return{id,contractId:id,eventId:'SYNTHETIC-EVENT',gameId:'2026_08_BAL_BUF',eventStart:'2026-11-01T18:00:00Z',playerId,playerName:'SYNTHETIC '+playerId,team:'BUF',opponent:'BAL',stat,threshold:40.5,operator:'gt',rulesHash:'SYNTHETIC-RULES',rules:'SYNTHETIC full-game threshold',provider:'Kalshi',sourceKind:'public_exchange',observedAt:now,quotedAt:null,mapping:{status:'verified'},verification:{current:true,quoteVerified:true,issues:[]},settlement:{rulesVerified:true,modelCompatible:true,fullGame:true,overtimeIncluded:true,unconditionalValuationSupported:false,statCoverage:'full_game_including_overtime'}};
}
function engine(body:any){
 const definitions=body.inputContext.contractDefinitions,contracts=definitions.map((definition:any)=>({id:definition.id,probability:.6,pushProbability:0,settlement:definition})),selected=body.inputContext.selectedOutcomes;
 return{result:{simulations:10000,home:'BUF',away:'BAL',modelVersion:'SYNTHETIC-PBP-MODEL',homeWinProbability:body.inputContext.whatIf?.status==='inactive'?.4:.6,awayWinProbability:body.inputContext.whatIf?.status==='inactive'?.6:.4,tieProbability:0,scoreDistributions:{BUF:{histogram:[{value:21,count:10000}]},BAL:{histogram:[{value:14,count:10000}]}},contracts,jointOutcomes:definitions.length===2?[{outcomes:['yes','yes'],count:5000},{outcomes:['yes','no'],count:1000},{outcomes:['no','yes'],count:1000},{outcomes:['no','no'],count:3000}]:definitions.length===1?[{outcomes:['yes'],count:6000},{outcomes:['no'],count:4000}]:[],combination:selected?{selectedOutcomes:selected,simulations:10000,jointProbability:Object.values(selected).every(side=>side==='yes')?.5:.1,independenceAssumptionProbability:Object.values(selected).reduce((n:number,side:any)=>n*(side==='yes'?.6:.4),1),pushAffectedProbability:0,monteCarloInterval95:[.49,.51],parameterInterval95:[.4,.6]}:null,...body.inputContext.whatIf?{hypothetical:{kind:'availability_what_if',assumptions:body.inputContext.whatIf}}:{},players:{},uncertainty:{parameterBootstrap:{combinationInterval95:[.4,.6]}}},research:{sources:[...s.detail.analysis.research.sources].reverse().map((source:any)=>({...source,checkedAt:'2026-10-30T21:00:12Z'}))}};
}
beforeEach(()=>{
 vi.useFakeTimers({toFake:['Date']});vi.setSystemTime(new Date(now));vi.stubEnv('SIMULATION_SERVICE_URL','https://worker.example.test/');vi.stubEnv('SIMULATION_SERVICE_TOKEN','SYNTHETIC-PRIVATE-KEY-01234567890123456789');s.jobs.clear();s.after=[];s.writes=[];s.quota=true;
 const one=contract('SYNTHETIC-CONTRACT-ONE','00-0000001'),two=contract('SYNTHETIC-CONTRACT-TWO','00-0000002');
 s.snapshots=[{id:first,data:{id:first,game:{id:one.gameId},contract:one,side:'YES',status:'conditional',stale:false,probability:{raw:.6},simulationId:'SYNTHETIC-BASELINE'}},{id:second,data:{id:second,game:{id:two.gameId},contract:two,side:'YES',status:'conditional',stale:false,probability:{raw:.6},simulationId:'SYNTHETIC-BASELINE'}}];s.contracts=[{id:one.id,data:one},{id:two.id,data:two}];
 s.detail={game:{id:one.gameId,startTime:one.eventStart,season:2026,week:8,status:'scheduled',home:{id:'BUF'},away:{id:'BAL'}},injuries:{items:[]},weather:{status:'unavailable'},analysis:{id:'SYNTHETIC-BASELINE',status:'completed',stale:false,result:{simulations:10000,modelVersion:'SYNTHETIC-PBP-MODEL',homeWinProbability:.6,awayWinProbability:.4,tieProbability:0},research:{sources:[{id:'nflverse-pbp',status:'available',version:'SYNTHETIC-PBP-V1'},{id:'nflverse-rosters',status:'available',version:'SYNTHETIC-ROSTER-V1'},{id:'nflverse-injuries',status:'available',version:'SYNTHETIC-INJURY-V1'}],playerCatalog:[{id:'00-0000001'},{id:'00-0000002'}]}}};
 vi.stubGlobal('fetch',vi.fn(async(_url:any,init:any)=>Response.json(engine(JSON.parse(init.body)))));
});
afterEach(()=>{vi.unstubAllGlobals();vi.unstubAllEnvs();vi.useRealTimers();});
describe('Private hypothetical player research',()=>{
 it('requires an app identity and actual session before accessing or reserving research',async()=>{
  await expect(queuePrivatePropResearch({...context(),user:null},'combination',{researchIds:[first,second]})).rejects.toMatchObject({status:401});
  await expect(queuePrivatePropResearch({...context(),accessToken:null},'combination',{researchIds:[first,second]})).rejects.toMatchObject({status:401});expect(s.writes).toEqual([]);
 });
 it('saves signed private selections before deferred compute and exposes only neutral global quota metadata',async()=>{
  const ctx=context(),job=await queuePrivatePropResearch(ctx,'combination',{researchIds:[first,second]});
  expect(job.status).toBe('queued');expect(job.actualWagerRecorded).toBe(false);expect(fetch).not.toHaveBeenCalled();expect(s.after).toHaveLength(1);expect(s.jobs.get(job.id).user_id).toBe(ctx.user.id);
  const shared=JSON.stringify(s.writes);expect(shared).not.toContain(ctx.user.id);expect(shared).not.toContain(first);expect(shared).not.toContain('SYNTHETIC-CONTRACT');expect(shared).not.toContain('selectedOutcomes');
  await s.after[0]();const complete=await readPrivatePropResearch(ctx,job.id);
  expect(complete.status).toBe('completed');expect(complete.provenanceVerified).toBe(true);expect(complete.result!.combination.jointProbability).toBe(.5);expect(complete.result!.combination.independenceAssumptionProbability).toBe(.36);expect(complete.result!.valuation.netExpectedValueCents).toBeNull();expect(()=>verifyCloudResult(ctx,job.id,complete)).not.toThrow();
  expect(s.writes.find(write=>write.action==='job_complete').result).toEqual({purpose:'private_research',simulations:10000});
 });
 it('evaluates requested NO legs on aligned outcomes while keeping the independence comparison separate',async()=>{
  const ctx=context(),job=await queuePrivatePropResearch(ctx,'combination',{researchIds:[first,second],sides:{[second]:'NO'}});await s.after[0]();const complete=await readPrivatePropResearch(ctx,job.id);expect(complete.status).toBe('completed');expect(complete.result!.combination.jointProbability).toBe(.1);expect(complete.result!.combination.independenceAssumptionProbability).toBe(.24);expect(complete.input.selections[1].side).toBe('NO');expect(complete.input.selections[1].baselineProbability).toBe(.4);
 });
 it('lists only verified owner-scoped summaries without dispatching queued history or exposing full private inputs',async()=>{
  const ctx=context(),job=await queuePrivatePropResearch(ctx,'combination',{researchIds:[first,second]});const count=s.after.length;
  const list=await listPrivatePropResearch(ctx,'combination');expect(list).toHaveLength(1);expect(list[0].id).toBe(job.id);expect(list[0]).not.toHaveProperty('input');expect(s.after).toHaveLength(count);expect(await listPrivatePropResearch(context('SYNTHETIC-OTHER'),'combination')).toEqual([]);
  await s.after[0]();s.jobs.get(job.id).data.result.combination.jointProbability=.99;expect((await listPrivatePropResearch(ctx,'combination'))[0].status).toBe('provenance_unverified');
 });
 it('retains owner isolation and rejects edited inputs or generated results',async()=>{
  const ctx=context(),job=await queuePrivatePropResearch(ctx,'combination',{researchIds:[first,second]});
  await expect(readPrivatePropResearch(context('SYNTHETIC-OTHER-OWNER'),job.id)).rejects.toMatchObject({status:404});
  s.jobs.get(job.id).data.input.simulations=100000;await expect(executePrivatePropResearch(ctx,job.id)).rejects.toMatchObject({status:422});expect(fetch).not.toHaveBeenCalled();
 });
 it('accepts only one fenced worker under duplicate dispatch and detects result tampering',async()=>{
  const ctx=context(),job=await queuePrivatePropResearch(ctx,'combination',{researchIds:[first,second]});
  await Promise.all([executePrivatePropResearch(ctx,job.id),executePrivatePropResearch(ctx,job.id)]);expect(fetch).toHaveBeenCalledOnce();
  s.jobs.get(job.id).data.result.combination.jointProbability=.99;await expect(readPrivatePropResearch(ctx,job.id)).rejects.toThrow(/provenance/);
 });
 it('withholds a scenario comparison when actual source versions change, ignoring harmless order/check timestamps',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(_url:any,init:any)=>{const value=engine(JSON.parse(init.body));value.research.sources[0].version='SYNTHETIC-NEW-INJURY-V2';return Response.json(value);}));
  const ctx=context(),job=await queuePrivatePropResearch(ctx,'what_if',{gameId:'2026_08_BAL_BUF',playerId:'00-0000001',status:'inactive'});await s.after[0]();const failed=await readPrivatePropResearch(ctx,job.id);expect(failed.status).toBe('failed');expect(failed.error).toMatch(/evidence or model version changed/);expect(failed.result).toBeNull();expect(JSON.stringify(s.writes)).not.toContain('00-0000001');
 });
 it('compares a verified same-evidence availability scenario without modifying current public records',async()=>{
  const prior=structuredClone(s.detail),ctx=context(),job=await queuePrivatePropResearch(ctx,'what_if',{gameId:'2026_08_BAL_BUF',playerId:'00-0000001',status:'inactive'});await s.after[0]();const complete=await readPrivatePropResearch(ctx,job.id);
  expect(complete.status).toBe('completed');expect(complete.result!.delta.homeWinProbability).toBeCloseTo(-.2);expect(complete.result!.currentVerifiedConditionsChanged).toBe(false);expect(s.detail).toEqual(prior);
 });
 it('rejects stale/mismapped/cross-game selections and unsupported threshold rules before charging compute',async()=>{
  s.contracts[0].data.mapping.status='unmapped';await expect(queuePrivatePropResearch(context(),'combination',{researchIds:[first,second]})).rejects.toMatchObject({status:422});expect(s.writes).toEqual([]);
  s.contracts[0].data.mapping.status='verified';s.contracts[0].data.observedAt='2026-10-30T20:00:00Z';await expect(queuePrivatePropResearch(context(),'combination',{researchIds:[first,second]})).rejects.toThrow(/no longer fresh/);
  s.contracts[0].data.observedAt=now;s.snapshots[1].data.game.id='2026_08_TEN_CIN';await expect(queuePrivatePropResearch(context(),'combination',{researchIds:[first,second]})).rejects.toThrow(/same complete simulated game/);expect(s.writes).toEqual([]);
 });
 it('withholds impossible or missing aligned joint outcomes rather than multiplying marginals',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(_url:any,init:any)=>{const value=engine(JSON.parse(init.body));value.result.jointOutcomes[0].count=4999;return Response.json(value);}));
  const ctx=context(),job=await queuePrivatePropResearch(ctx,'combination',{researchIds:[first,second]});await s.after[0]();const failed=await readPrivatePropResearch(ctx,job.id);expect(failed.status).toBe('failed');expect(failed.error).toMatch(/joint outcome counts/);expect(failed.result).toBeNull();
 });
 it('values only an explicit fully modeled combined offer without charging the stated fees twice',async()=>{
  for(const row of s.contracts)row.data.settlement.unconditionalValuationSupported=true;
  const offer={verified:true,source:'SYNTHETIC user-verified combined quote',quotedAt:now,totalStake:'10.50',combinedPayout:'40.00',fees:'0.50',settlementRules:'SYNTHETIC all selected outcomes win; total debit and net receipt include all costs.',settlementComplete:true};
  const ctx=context(),job=await queuePrivatePropResearch(ctx,'combination',{researchIds:[first,second],offer});await s.after[0]();const complete=await readPrivatePropResearch(ctx,job.id);expect(complete.result!.valuation.netExpectedValueCents).toBe('950.00000000');expect(complete.result!.valuation.executionVerified).toBe(false);
 });
 it('withholds value for unmodeled non-participation even when a combined offer is manually supplied',async()=>{
  const ctx=context(),job=await queuePrivatePropResearch(ctx,'combination',{researchIds:[first,second],offer:{verified:true,source:'SYNTHETIC user quote',quotedAt:now,totalStake:'10.00',combinedPayout:'40.00',fees:'0.00',settlementRules:'SYNTHETIC user description of a hypothetical combined offer.',settlementComplete:true}});await s.after[0]();const complete=await readPrivatePropResearch(ctx,job.id);expect(complete.result!.valuation.netExpectedValueCents).toBeNull();expect(complete.result!.valuation.reason).toMatch(/Non-participation/);
 });
 it('does not publish a pregame comparison after kickoff passed during backend computation',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(_url:any,init:any)=>{const result=engine(JSON.parse(init.body));vi.setSystemTime(new Date('2026-11-01T18:00:01Z'));return Response.json(result);}));
  const ctx=context(),job=await queuePrivatePropResearch(ctx,'combination',{researchIds:[first,second]});await s.after[0]();const failed=await readPrivatePropResearch(ctx,job.id);expect(failed.status).toBe('failed');expect(failed.errorStatus).toBe(409);expect(failed.result).toBeNull();
 });
 it('retains saved input when a supported cohort is unavailable or global compute is exhausted',async()=>{
  s.quota=false;const ctx=context(),job=await queuePrivatePropResearch(ctx,'what_if',{gameId:'2026_08_BAL_BUF',playerId:'00-0000001',status:'limited'});await s.after[0]();expect((await readPrivatePropResearch(ctx,job.id)).errorStatus).toBe(429);expect(fetch).not.toHaveBeenCalled();
  s.quota=true;vi.stubGlobal('fetch',vi.fn(async()=>Response.json({detail:'SYNTHETIC limited cohort has insufficient historical evidence'},{status:422})));const unsupported=await queuePrivatePropResearch(ctx,'what_if',{gameId:'2026_08_BAL_BUF',playerId:'00-0000001',status:'limited'});await s.after.at(-1)!();const failed=await readPrivatePropResearch(ctx,unsupported.id);expect(failed.errorStatus).toBe(422);expect(failed.result).toBeNull();
 });
});
