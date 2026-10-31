import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest';
import {playerPropFixture} from './fixtures/player-props';
const s=vi.hoisted(()=>({run:null as any,after:[] as Array<()=>Promise<void>>,game:null as any,detail:null as any,complete:null as any,discovery:null as any,refreshed:null as any,contracts:new Map<string,any>(),snapshots:new Map<string,any>(),runRows:new Map<string,Set<string>>(),jobs:new Map<string,any>(),counter:0}));
const source=vi.hoisted(()=>({loadSchedule:vi.fn(),publicGameDetail:vi.fn(),analyzePublicGame:vi.fn()}));
const provider=vi.hoisted(()=>({discoverPlayerPropMarkets:vi.fn(),fetchPlayerPropMarkets:vi.fn(),draftKingsFeedConfigured:vi.fn(()=>true)}));
const storage=vi.hoisted(()=>({propWrite:vi.fn(),storeContracts:vi.fn(),storeResearch:vi.fn(),cachedGameStates:vi.fn()}));
const publicStorage=vi.hoisted(()=>({latestJobs:vi.fn()}));
const lab=vi.hoisted(()=>({getPropPerformance:vi.fn()}));
vi.mock('next/server',()=>({after:(work:()=>Promise<void>)=>s.after.push(work)}));
vi.mock('../lib/public-nfl/service',()=>({...source,PUBLIC_PIPELINE_VERSION:'public-nfl-6.0.0',evidenceHash:()=> 'SYNTHETIC-VERIFIED-INPUT'}));
vi.mock('../lib/public-nfl/store',()=>({sharedJob:vi.fn(async(id:string)=>s.jobs.get(id)??null),...publicStorage}));
vi.mock('../lib/player-props/providers',()=>provider);
vi.mock('../lib/player-props/model-lab',()=>({...lab,loadApprovedPropCalibrators:async()=>new Map()}));
vi.mock('../lib/player-props/store',()=>({
 ...storage,propRun:vi.fn(async(id?:string)=>!id||s.run?.id===id?structuredClone(s.run):null),propBatch:vi.fn(),
 storedContracts:vi.fn(async(gameId:string)=>[...s.contracts.values()].filter(row=>row.gameId===gameId).map(row=>structuredClone(row))),
 researchPage:vi.fn(async(runId:string,filter:any={})=>{let rows=[...s.runRows.get(runId)??[]].map(id=>structuredClone(s.snapshots.get(id)));if(filter.side)rows=rows.filter(row=>row.side===filter.side);return{rows:rows.slice(Number(filter.cursor??0),Number(filter.cursor??0)+(filter.limit??60)),total:rows.length,nextCursor:null};}),
 currentContracts:vi.fn(async(ids:string[])=>new Map(ids.filter(id=>s.contracts.has(id)).map(id=>[id,structuredClone(s.contracts.get(id))]))),
 storedResearch:vi.fn(async(id:string)=>structuredClone(s.snapshots.get(id)??null)),
 contractDefinitionHash:(row:any)=>JSON.stringify([row.id,row.gameId,row.eventId,row.playerId,row.stat,row.threshold,row.operator,row.rulesHash,row.eventStart]),
 contractQuoteHash:(row:any)=>JSON.stringify([row.yesAskCents,row.noAskCents,row.observedAt]),
}));
import {startPropScan,executePropRun,propDashboard,nflMarketDashboard,propResearchDetail,hydrateCurrent,refreshPropResearch} from '../lib/player-props/service';

const now='2026-10-30T21:21:51.293Z';
beforeEach(()=>{
 vi.useFakeTimers({toFake:['Date']});vi.setSystemTime(new Date(now));vi.clearAllMocks();
 lab.getPropPerformance.mockResolvedValue({status:'insufficient_evidence',eligibleResolved:0,overall:null});
 provider.draftKingsFeedConfigured.mockReturnValue(true);
 const fixture=playerPropFixture(),contract=structuredClone(fixture.receiverYes.contract),detail:any=structuredClone(fixture.nfl.detail);
 detail.game={...detail.game,id:'2026_08_BAL_BUF',home:{id:'BUF',abbreviation:'BUF',name:'SYNTHETIC Home'},away:{id:'BAL',abbreviation:'BAL',name:'SYNTHETIC Away'}};
 Object.assign(contract,{gameId:detail.game.id,team:'BAL',opponent:'BUF',playerId:null});
 detail.analysis.gameId=detail.game.id;detail.analysis.inputHash='SYNTHETIC-VERIFIED-INPUT';
 detail.analysis.research={version:'automatic-nfl-research-6.0.0',playerCatalog:[{id:'00-0000001',name:contract.playerName,team:'BAL',position:'WR',rosterWeek:8}],injuryImpact:{fullyAdjusted:false}};
 Object.assign(detail.analysis.result,{distributionEncoding:'exact_integer_frequency_v1',engineVersion:'pbp-runtime-6.0.0',players:{'00-0000001':{receivingYards:{histogram:[{value:0,count:2000},{value:64,count:3000},{value:65,count:5000}]}}}});
 s.run=null;s.after=[];s.game=detail.game;s.detail=detail;s.complete=structuredClone(detail);s.counter=0;s.contracts.clear();s.snapshots.clear();s.runRows.clear();s.jobs.clear();
 s.jobs.set(detail.analysis.id,{result:{result:detail.analysis.result}});
 s.discovery={contracts:[contract],providers:fixture.scan.providers,sources:fixture.scan.sources,checkedAt:now,complete:true,rejected:[],neededGames:[]};s.refreshed=structuredClone(s.discovery);
 source.loadSchedule.mockImplementation(async()=>({games:[s.game],sources:[],updatedAt:new Date().toISOString(),inputVersion:'SYNTHETIC-SCHEDULE'}));
 source.publicGameDetail.mockImplementation(async()=>structuredClone(s.detail));
 source.analyzePublicGame.mockImplementation(async()=>{s.detail={...s.detail,analysis:{...s.complete.analysis,status:'queued',result:null,research:null}};return structuredClone(s.detail);});
 storage.cachedGameStates.mockResolvedValue(new Map());publicStorage.latestJobs.mockResolvedValue([]);
 provider.discoverPlayerPropMarkets.mockImplementation(async()=>structuredClone(s.discovery));provider.fetchPlayerPropMarkets.mockImplementation(async()=>structuredClone(s.refreshed));
 storage.propWrite.mockImplementation(async(payload:any)=>{
  if(payload.action==='run_enqueue'){s.run={id:'SYNTHETIC-RUN-'+(++s.counter),status:'queued',data:structuredClone(payload.data),result:null,error:null,lease:null,created_at:new Date().toISOString(),updated_at:new Date().toISOString()};return structuredClone(s.run);}
  if(payload.action==='run_claim'){if(!s.run||s.run.id!==payload.id||s.run.status!=='queued')return null;s.run.status='running';s.run.lease=payload.lease;return structuredClone(s.run);}
  if(payload.action==='run_checkpoint'){if(s.run?.lease!==payload.lease)throw Error('SYNTHETIC stale lease');Object.assign(s.run,{data:structuredClone(payload.data),result:structuredClone(payload.result),status:payload.status,error:payload.error??null,updated_at:new Date().toISOString()});return structuredClone(s.run);}
  throw Error('Unexpected synthetic storage action');
 });
 storage.storeContracts.mockImplementation(async(contracts:any[])=>contracts.map(contract=>{s.contracts.set(contract.id,structuredClone(contract));return{id:contract.id,quoteId:'SYNTHETIC-QUOTE-'+contract.yesAskCents};}));
 storage.storeResearch.mockImplementation(async(rows:any[],_quoteIds:any,runId:string)=>{const ids=s.runRows.get(runId)??new Set<string>();for(const row of rows){if(!s.snapshots.has(row.id))s.snapshots.set(row.id,{...structuredClone(row),distribution:null});ids.add(row.id);}s.runRows.set(runId,ids);return rows.map(row=>({id:row.id}));});
});
afterEach(()=>vi.useRealTimers());

async function discoveredRun(){const run=await startPropScan();expect(s.after).toHaveLength(1);await s.after.shift()!();return run;}
async function completedRun(){const run=await discoveredRun();await executePropRun(run.id);return run;}

describe('Automatic persistent player-prop research state machine',()=>{
 it('returns an explicit primary-feed limitation without source calls, shared writes or hidden alternative simulation work',async()=>{
  provider.draftKingsFeedConfigured.mockReturnValue(false);vi.stubEnv('GRIDIRON_KALSHI_BACKGROUND_RESEARCH','');
  const page=await nflMarketDashboard();expect(page.status).toBe('unavailable');expect(page.providers[0].provider).toBe('DraftKings Predictions');expect(page.results).toEqual([]);expect(page.runId).toBeNull();expect(s.after).toHaveLength(0);expect(storage.propWrite).not.toHaveBeenCalled();expect(source.publicGameDetail).not.toHaveBeenCalled();expect(provider.discoverPlayerPropMarkets).not.toHaveBeenCalled();expect((await refreshPropResearch()).status).toBe('unavailable');expect(storage.propWrite).not.toHaveBeenCalled();
  await expect(startPropScan()).rejects.toMatchObject({status:503});expect(storage.propWrite).not.toHaveBeenCalled();vi.unstubAllEnvs();
 });
 it('applies the same DraftKings-only default to the legacy player API even when an alternative run exists',async()=>{
  provider.draftKingsFeedConfigured.mockReturnValue(false);s.run={id:'SYNTHETIC-EXPLICIT-ALTERNATIVE',status:'queued',data:{provider:'Kalshi',pipelineVersion:'nfl-event-contract-research-7.0.0'},updated_at:now};
  const page=await propDashboard();expect(page.status).toBe('unavailable');expect(page.runId).toBeNull();expect(page.results).toEqual([]);expect(s.after).toHaveLength(0);expect(storage.propWrite).not.toHaveBeenCalled();expect(provider.discoverPlayerPropMarkets).not.toHaveBeenCalled();
 });
 it('continues an explicitly selected alternative job after the phone closes without enabling new alternative scans',async()=>{
  provider.draftKingsFeedConfigured.mockReturnValue(false);vi.stubEnv('GRIDIRON_KALSHI_BACKGROUND_RESEARCH','');
  const run=await startPropScan('user','Kalshi');s.after=[];
  expect(await refreshPropResearch()).toMatchObject({id:run.id,status:'continued'});
  expect(provider.discoverPlayerPropMarkets).toHaveBeenCalledWith([s.game],{includeGameMarkets:true,provider:'Kalshi'});
  s.run.status='completed';const count=s.counter;
  expect((await refreshPropResearch()).status).toBe('unavailable');expect(s.counter).toBe(count);vi.unstubAllEnvs();
 });
 it('discovers authorized contracts before scheduling one backend10k job and publishes only complete verified results',async()=>{
  s.detail.analysis=null;const run=await discoveredRun();
  expect(provider.discoverPlayerPropMarkets).toHaveBeenCalledWith([s.game],{includeGameMarkets:true,provider:'DraftKings Predictions'});expect(s.run.data.phase).toBe('research');expect(s.run.status).toBe('queued');expect(s.snapshots.size).toBe(0);
  await executePropRun(run.id);expect(source.analyzePublicGame).toHaveBeenCalledOnce();expect(source.analyzePublicGame).toHaveBeenCalledWith(s.game.id);expect(s.run.status).toBe('queued');expect(s.snapshots.size).toBe(0);
  await executePropRun(run.id);expect(source.analyzePublicGame).toHaveBeenCalledOnce();expect(s.snapshots.size).toBe(0);
  s.detail=structuredClone(s.complete);await executePropRun(run.id);
  expect(s.run.status).toBe('completed');expect(s.snapshots.size).toBe(2);
  const dashboard=await propDashboard();expect(dashboard.totalResults).toBe(2);expect(dashboard.results.map(row=>row.probability.raw).sort()).toEqual([.5,.5]);expect(dashboard.results.every(row=>row.probability.calibrated===null)).toBe(true);expect(dashboard.results.every(row=>row.valuation.netValueCents===null)).toBe(true);
 });
 it('reuses the current scan under concurrent requests and does not duplicate source work under a leased phase',async()=>{
  const first=await startPropScan(),repeated=await startPropScan();expect(repeated.id).toBe(first.id);expect(storage.propWrite.mock.calls.filter(([payload])=>payload.action==='run_enqueue')).toHaveLength(1);
  await Promise.all([executePropRun(first.id),executePropRun(first.id)]);expect(provider.discoverPlayerPropMarkets).toHaveBeenCalledOnce();
 });
 it('retains frozen prediction IDs and original captured prices while exposing a separate updated quote',async()=>{
  await completedRun();const stored=[...s.snapshots.values()][0],oldPrice=stored.contract.yesAskCents,oldProbability=stored.probability.raw;
  s.contracts.set(stored.contract.id,{...s.contracts.get(stored.contract.id),yesAskCents:'75',observedAt:new Date().toISOString()});
  const fresh=await propResearchDetail(stored.id);expect(fresh.id).toBe(stored.id);expect(fresh.contract.yesAskCents).toBe(oldPrice);expect(fresh.currentContract!.yesAskCents).toBe('75');expect(fresh.probability.raw).toBe(oldProbability);expect(fresh.distribution!.histogram.reduce((n,p)=>n+p.count,0)).toBe(10000);expect(s.snapshots.get(stored.id).contract.yesAskCents).toBe(oldPrice);
  vi.setSystemTime(new Date(Date.parse(now)+100000));s.discovery.contracts[0].observedAt=new Date().toISOString();s.refreshed.contracts[0].observedAt=new Date().toISOString();s.refreshed.contracts[0].yesAskCents='75';
  const next=await completedRun();expect(next.id).not.toBe(stored.runId);expect(s.snapshots.size).toBe(2);expect(source.analyzePublicGame).not.toHaveBeenCalled();expect(s.snapshots.get(stored.id).contract.yesAskCents).toBe(oldPrice);
 });
 it('withholds malformed or unavailable distributions instead of interpreting them as zero',async()=>{
  s.detail.analysis.result.players={};await completedRun();const rows=[...s.snapshots.values()];expect(rows).toHaveLength(2);expect(rows.every(row=>row.status==='withheld'&&row.probability.raw===null)).toBe(true);expect(rows.every(row=>row.withheldReasons.join(' ').includes('distribution'))).toBe(true);
 });
 it('reports unavailable or failed providers explicitly without inventing quotes, games or predictions',async()=>{
  s.discovery.contracts=[];const unavailable=await discoveredRun();expect(s.run.status).toBe('unavailable');expect(s.snapshots.size).toBe(0);expect(source.analyzePublicGame).not.toHaveBeenCalled();
  vi.setSystemTime(new Date(Date.parse(now)+100000));provider.discoverPlayerPropMarkets.mockRejectedValueOnce(new Error('SYNTHETIC source outage'));const failed=await startPropScan();await executePropRun(failed.id);expect(failed.id).not.toBe(unavailable.id);expect(s.run.status).toBe('failed');expect(s.run.error).toMatch(/No replacement prices or probabilities were invented/);expect(s.snapshots.size).toBe(0);
 });
 it('flags historical model inputs and changed settlement thresholds before comparing fresh prices',async()=>{
  await completedRun();const row=structuredClone([...s.snapshots.values()][0]);
  const changed={...row.contract,threshold:row.contract.threshold+1,yesAskCents:'20'};
  const invalid=hydrateCurrent(row,changed);expect(invalid.stale).toBe(true);expect(invalid.currentValuation!.netValueCents).toBeNull();expect(invalid.currentValuation!.reason).toMatch(/definition|settlement|threshold|rules/i);expect(invalid.contract.threshold).toBe(row.contract.threshold);
  s.detail.analysis.id='20000000-0000-4000-8000-000000000006';const historical=await propResearchDetail(row.id);expect(historical.stale).toBe(true);expect(historical.currentValuation!.netValueCents).toBeNull();expect(historical.probability.raw).toBe(row.probability.raw);
 });
 it('withholds current comparisons after failed source verification or changed injury inputs despite fresh quotes',async()=>{
  await completedRun();const row=[...s.snapshots.values()][0],hash='SYNTHETIC-VERIFIED-INPUT',job={id:row.simulationId,game_id:row.game.id,input_hash:hash,status:'completed',data:{simulations:10000}};
  publicStorage.latestJobs.mockResolvedValue([job]);
  storage.cachedGameStates.mockResolvedValue(new Map([[row.game.id,{pipeline:'public-nfl-6.0.0',verified:'false',updated_at:now,input_hash:hash}]]));
  const outage=await propDashboard();expect(outage.results.every(value=>value.stale&&value.currentValuation?.netValueCents===null)).toBe(true);expect(outage.results[0].probability.raw).toBe(row.probability.raw);
  storage.cachedGameStates.mockResolvedValue(new Map([[row.game.id,{pipeline:'public-nfl-6.0.0',verified:'true',updated_at:now,input_hash:'SYNTHETIC-VERIFIED-NEW-INJURY'}]]));
  publicStorage.latestJobs.mockImplementation(async(_limit:number,hashes?:string[])=>hashes?[]:[job]);
  const changed=await propDashboard();expect(changed.results.every(value=>value.stale&&value.currentValuation?.breakEven===null)).toBe(true);expect(s.snapshots.get(row.id).probability.raw).toBe(row.probability.raw);
 });
 it('recovers the exact current verified simulation instead of allowing a newer outage failure to shadow it',async()=>{
  await completedRun();const row=[...s.snapshots.values()][0],hash='SYNTHETIC-VERIFIED-INPUT',valid={id:row.simulationId,game_id:row.game.id,input_hash:hash,status:'completed',data:{simulations:10000}},failure={id:'SYNTHETIC-NEWER-FAILED-JOB',game_id:row.game.id,input_hash:'SYNTHETIC-OUTAGE-HASH',status:'failed',data:{simulations:10000}};
  storage.cachedGameStates.mockResolvedValue(new Map([[row.game.id,{pipeline:'public-nfl-6.0.0',verified:'true',updated_at:now,input_hash:hash}]]));
  publicStorage.latestJobs.mockImplementation(async(_limit:number,hashes?:string[])=>hashes?[valid]:[failure,valid]);
  const recovered=await propDashboard();expect(recovered.results.every(value=>!value.stale&&value.status===s.snapshots.get(value.id).status)).toBe(true);expect(recovered.results[0].simulationId).toBe(row.simulationId);expect(publicStorage.latestJobs).toHaveBeenCalledWith(100,[hash]);expect(source.analyzePublicGame).not.toHaveBeenCalled();
 });
 it('expires a quote at response time when a slow historical-metrics lookup crosses its freshness limit',async()=>{
  await completedRun();const row=[...s.snapshots.values()][0],hash='SYNTHETIC-VERIFIED-INPUT',valid={id:row.simulationId,game_id:row.game.id,input_hash:hash,status:'completed',data:{simulations:10000}};
  storage.cachedGameStates.mockResolvedValue(new Map([[row.game.id,{pipeline:'public-nfl-6.0.0',verified:'true',updated_at:now,input_hash:hash}]]));publicStorage.latestJobs.mockResolvedValue([valid]);
  lab.getPropPerformance.mockImplementation(async()=>{vi.setSystemTime(new Date(Date.parse(now)+121000));return{status:'pending',overall:null};});
  const page=await propDashboard();expect(page.results.every(value=>value.currentContract!.verification.current===false&&value.stale&&value.currentValuation?.netValueCents===null)).toBe(true);expect(page.results[0].contract.observedAt).toBe(row.contract.observedAt);expect(page.results[0].probability.raw).toBe(row.probability.raw);
 });
 it('can compare a newly verified quote with the same current model without rewriting the old expired capture',async()=>{
  await completedRun();const row=structuredClone([...s.snapshots.values()][0]);row.stale=true;row.status='stale';const original=structuredClone(row),current={...row.contract,yesAskCents:'63',observedAt:new Date().toISOString()};const fresh=hydrateCurrent(row,current);expect(fresh.stale).toBe(false);expect(fresh.status).toBe('conditional');expect(fresh.probability.raw).toBe(original.probability.raw);expect(row).toEqual(original);expect(fresh.contract.yesAskCents).toBe(original.contract.yesAskCents);expect(fresh.currentContract!.yesAskCents).toBe('63');
 });
});
