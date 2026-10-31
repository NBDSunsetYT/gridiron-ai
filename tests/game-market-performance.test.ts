import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest';
/** Explicit SYNTHETIC settlement/ownership fixtures; never production NFL data. */
const state=vi.hoisted(()=>({predictions:[] as any[],resolutions:[] as any[],cache:new Map<string,any>(),writes:[] as any[],queries:[] as any[],sourceCalls:0,schedule:'',archiveError:false,sourceError:false,declaredCount:null as number|null}));
vi.mock('../lib/cloud/context',()=>({cloudClient:()=>({from:(table:string)=>{
 const filters:Record<string,any>={};const query:any={select:(columns:string,options:any)=>{state.queries.push({table,columns,options});return query;},in:(key:string,value:any)=>{filters[key]=value;return query;},not:()=>query,order:()=>query,
 range:async(start:number,end:number)=>{if(state.archiveError)return{data:[],count:null,error:{message:'SYNTHETIC storage failure'}};
  const source=table==='shared_prop_snapshots'?state.predictions.filter(row=>filters.category?.includes(row.category)&&row.raw_probability!==null):state.resolutions.filter(row=>filters.prediction_id?.includes(row.prediction_id??row.predictionId));
  return{data:structuredClone(source.slice(start,end+1)),count:table==='shared_prop_snapshots'?state.declaredCount??source.length:source.length,error:null};}};return query;
}})}));
vi.mock('../lib/player-props/store',()=>({propWrite:vi.fn(async(input:any)=>{state.writes.push(structuredClone(input));if(input.action==='resolutions_put')for(const row of input.resolutions)state.resolutions.push({id:row.id,prediction_id:row.predictionId,status:row.status,observed_value:row.observedValue,resolved_at:row.resolvedAt,available_at:row.availableAt,source_url:row.sourceUrl,source_version:row.sourceVersion,verified_final:row.verifiedFinal,previous_resolution_id:row.previousResolutionId,data:structuredClone(row)});return input.resolutions;})}));
vi.mock('../lib/public-nfl/store',()=>({sharedCache:vi.fn(async(kind:string,key:string)=>state.cache.get(kind+':'+key)??null),putCache:vi.fn(async(kind:string,key:string,data:any,inputHash:string,ttl:number)=>{state.cache.set(kind+':'+key,{data:structuredClone(data),input_hash:inputHash,expires_at:new Date(Date.now()+ttl).toISOString()});}),fresh:(value:any)=>Boolean(value&&Date.parse(value.expires_at)>Date.now())}));
vi.mock('../lib/public-nfl/sources',async original=>{const real:any=await original();return{...real,boundedFetch:vi.fn(async()=>{state.sourceCalls++;if(state.sourceError)throw Error('SYNTHETIC final source unavailable');return{body:Buffer.from(state.schedule),headers:new Headers()};})};});

const NOW='2026-10-30T20:00:00Z';
const source=()=>({url:'https://example.invalid/SYNTHETIC-final-score',version:'SYNTH-SOURCE-V1',checkedAt:NOW});
function contract(){return{id:'SYNTH-CONTRACT',contractId:'SYNTH-PROVIDER-CONTRACT',eventId:'SYNTH-EVENT',gameId:'2026_01_BAL_BUF',eventStart:'2026-09-13T17:00:00Z',provider:'Kalshi',sourceKind:'public_exchange',playerId:null,playerName:'Buffalo',team:'BUF',opponent:'BAL',stat:'gameWinner',subject:{kind:'team',teamId:'BUF'},threshold:0,operator:'gt',rulesHash:'SYNTH-RULES-V1',observedAt:'2026-09-13T14:59:30Z',yesAskCents:'40',noAskCents:'65',verification:{current:true,quoteVerified:true},mapping:{status:'verified'},settlement:{rulesVerified:true,modelCompatible:true,fullGame:true,overtimeIncluded:true,payoutCents:'100',tiePayoutCents:'50',exceptionPolicy:'fair_price',unconditionalValuationSupported:false},fees:{calculationStatus:'unverified'}};}
function prediction(extra:any={}){return{id:'SYNTH-PREDICTION',game_id:'2026_01_BAL_BUF',category:'gameWinner',side:'YES',threshold:0,operator:'gt',raw_probability:.4,model_version:'SYNTH-MODEL-V7',input_version:'SYNTH-INPUT-V1',captured_at:'2026-09-13T15:00:00Z',created_at:'2026-09-13T15:00:01Z',event_start:'2026-09-13T17:00:00Z',contract:contract(),sources:[{id:'SYNTH-SOURCE',checkedAt:'2026-09-13T14:00:00Z'}],...extra};}
function game(scores=[24,17]){return{id:'2026_01_BAL_BUF',season:2026,week:1,startTime:'2026-09-13T17:00:00Z',status:'final',home:{id:'BUF',name:'Buffalo',abbreviation:'BUF',score:scores[0]},away:{id:'BAL',name:'Baltimore',abbreviation:'BAL',score:scores[1]},sources:[]} as any;}
async function resolution(row:any,scores=[24,17],extra:any={}){const lab=await import('../lib/player-props/game-performance'),outcome=lab.resolveGameMarketResearch(row,game(scores),source());return{...outcome,id:'SYNTH-RESOLUTION-'+row.id,predictionId:row.id,rulesHash:row.contract.rulesHash,resolvedAt:NOW,availableAt:NOW,sourceUrl:source().url,sourceVersion:source().version,verifiedFinal:true,previousResolutionId:null,...extra};}
beforeEach(()=>{vi.resetModules();vi.clearAllMocks();vi.useFakeTimers({toFake:['Date']});vi.setSystemTime(new Date(NOW));state.predictions=[];state.resolutions=[];state.cache.clear();state.writes=[];state.queries=[];state.sourceCalls=0;state.archiveError=false;state.sourceError=false;state.declaredCount=null;state.schedule='game_id,season,week,gameday,gametime,home_team,away_team,home_score,away_score,stadium\n2026_01_BAL_BUF,2026,1,2026-09-13,13:00,BUF,BAL,24,17,SYNTHETIC test stadium\n';});
afterEach(()=>vi.useRealTimers());
describe('Independent prospective game-contract final-score auditor',()=>{
 it('audits exact game subjects and prospective archives without inventing a player identity',async()=>{
  const lab=await import('../lib/player-props/game-performance'),row=prediction();expect(lab.auditGameMarketPrediction(row)).toEqual([]);
  for(const edit of[{created_at:'2026-09-13T18:00:00Z'},{raw_probability:true},{input_version:''},{sources:[]},{contract:{...row.contract,playerId:'INVENTED-GSIS'}},{contract:{...row.contract,settlement:{...row.contract.settlement,overtimeIncluded:false}}},{contract:{...row.contract,threshold:1}}])expect(lab.auditGameMarketPrediction({...row,...edit}).length).toBeGreaterThan(0);
  expect(lab.auditGameMarketPrediction({...row,sources:[{checkedAt:'2026-09-13T16:00:00Z'}]})).toContain('unverified_pre_prediction_input_availability');
 });
 it('scores YES and NO selected full-payout targets independently for partial ties',async()=>{
  const lab=await import('../lib/player-props/game-performance'),yes=prediction(),no=prediction({id:'SYNTH-NO',side:'NO',raw_probability:.5});
  const yesResult=await resolution(yes,[20,20]),noResult=await resolution(no,[20,20]);
  expect(yesResult).toMatchObject({status:'no',actualFullPayoutHit:0,partialPayoutCents:'50',outcomeBasis:'selected_side_full_payout',selectedSide:'YES',exchangeSettlementVerified:false});
  expect(noResult).toMatchObject({status:'no',actualFullPayoutHit:0,partialPayoutCents:'50',selectedSide:'NO'});
  const score=lab.evaluateGameMarketHistory([yes,no],[yesResult,noResult]);expect(score).toMatchObject({sampleSize:2,partialTieObservations:2,calibratedSampleSize:0,calibratedProbabilitiesAvailable:false});expect(score.overall.raw.brier).toBeCloseTo(.205);expect(score.overall.raw.observedRate).toBe(0);expect(score.overall.calibrated).toBeNull();expect(score.overall.market).toBeNull();
 });
 it('uses away-team margins and exact integer binary equality rules rather than sportsbook pushes',async()=>{
  const lab=await import('../lib/player-props/game-performance');
  const away=prediction({category:'spread',threshold:-7,operator:'gte',contract:{...contract(),stat:'spread',threshold:-7,operator:'gte',team:'BAL',opponent:'BUF',subject:{kind:'team',teamId:'BAL'}}});
  expect(lab.resolveGameMarketResearch(away,game(),source())).toMatchObject({status:'yes',observedValue:-7,actualFullPayoutHit:1});
  const total=prediction({category:'totalPoints',threshold:41,contract:{...contract(),stat:'totalPoints',threshold:41,subject:{kind:'game',teamId:null}}});
  expect(lab.resolveGameMarketResearch(total,game(),source())).toMatchObject({status:'no',observedValue:41});expect(lab.resolveGameMarketResearch({...total,side:'NO'},game(),source())).toMatchObject({status:'yes',observedValue:41});
  const team=prediction({category:'teamTotal',threshold:17,operator:'gte',contract:{...away.contract,stat:'teamTotal',threshold:17,operator:'gte'}});
  expect(lab.resolveGameMarketResearch(team,game(),source())).toMatchObject({status:'yes',observedValue:17});
 });
 it('withholds mismatched games, teams, nonfinal scores, immature outcomes and unverified timestamps',async()=>{
  const lab=await import('../lib/player-props/game-performance'),row=prediction();
  for(const final of[{...game(),id:'2026_02_BAL_BUF'},{...game(),status:'scheduled'},{...game(),home:{...game().home,score:null}},{...game(),home:{...game().home,id:'KC'}}])expect(lab.resolveGameMarketResearch(row,final,source()).status).toBe('unresolved');
  expect(lab.resolveGameMarketResearch(row,game(),{...source(),checkedAt:'2026-09-01T00:00:00Z'}).status).toBe('unresolved');
  const fresh=prediction({event_start:'2026-10-30T15:00:00Z',contract:{...contract(),eventStart:'2026-10-30T15:00:00Z'}});expect(lab.resolveGameMarketResearch(fresh,{...game(),startTime:fresh.event_start},source()).reason).toBe('final_game_not_mature');
 });
 it('recomputes archived resolution targets and rejects wrong rules or ambiguous corrections',async()=>{
  const lab=await import('../lib/player-props/game-performance'),row=prediction(),valid=await resolution(row);
  for(const edit of[{rulesHash:'OTHER-RULES'},{selectedSide:'NO'},{threshold:3.5},{actualFullPayoutHit:0},{finalScores:{...valid.finalScores,home:0}}]){
   const result=lab.evaluateGameMarketHistory([row],[{...valid,...edit}]);expect(result.sampleSize).toBe(0);expect(result.coverage.unresolvedPredictions).toBe(1);
  }
  const badChain={...valid,id:'SYNTH-UNLINKED',resolvedAt:'2026-10-30T20:00:01Z',previousResolutionId:null};expect(lab.evaluateGameMarketHistory([row],[valid,badChain]).excludedCounts).toHaveProperty('ambiguous_resolution_correction');
 });
 it('compares only captured binary prices with verified costs and never derives a full-hit baseline from partial-tie prices',async()=>{
  const lab=await import('../lib/player-props/game-performance'),row=prediction();row.contract.settlement={...row.contract.settlement,tiePayoutCents:'0',unconditionalValuationSupported:true};row.contract.fees={calculationStatus:'verified_explicit',entryFeeCents:'1',winFeeCents:'0',rounding:'none'};
  const result=lab.evaluateGameMarketHistory([row],[await resolution(row)]);expect(result.overall.marketComparison.commonSampleSize).toBe(1);expect(result.overall.market.predictedRate).toBeCloseTo(.41);expect(result.overall.market.brier).toBeCloseTo((1-.41)**2);
  row.contract.settlement.tiePayoutCents='50';const partial=lab.evaluateGameMarketHistory([row],[await resolution(row)]);expect(partial.overall.market).toBeNull();expect(partial.overall.marketComparison.commonSampleSize).toBe(0);
  row.contract.settlement.tiePayoutCents='0';row.contract.fees.calculationStatus='unverified';expect(lab.evaluateGameMarketHistory([row],[await resolution(row)]).overall.market).toBeNull();
 });
 it('reports game-block confidence and separate category/model/date windows without fitting a calibrator',async()=>{
  const lab=await import('../lib/player-props/game-performance'),rows:any[]=[],outcomes:any[]=[];
  for(let i=0;i<8;i++){
   const event=new Date(Date.parse('2026-09-13T17:00:00Z')+i*86400000).toISOString(),gameId=`2026_${String(i+1).padStart(2,'0')}_BAL_BUF`,row=prediction({id:'SYNTH-PREDICTION-'+i,game_id:gameId,raw_probability:.2+i*.075,event_start:event,captured_at:new Date(Date.parse(event)-7200000).toISOString(),created_at:new Date(Date.parse(event)-7199000).toISOString(),contract:{...contract(),id:'SYNTH-CONTRACT-'+i,gameId,eventStart:event}});
   const final={...game(),id:gameId,startTime:event},outcome=lab.resolveGameMarketResearch(row,final,source());rows.push(row);outcomes.push({...outcome,id:'SYNTH-FINAL-'+i,predictionId:row.id,rulesHash:row.contract.rulesHash,resolvedAt:NOW,availableAt:NOW,sourceUrl:source().url,sourceVersion:source().version,verifiedFinal:true,previousResolutionId:null});
  }
  const report=lab.evaluateGameMarketHistory(rows,outcomes);expect(report.overall.raw.games).toBe(8);expect(report.overall.raw.brierInterval95).toHaveLength(2);expect(report.overall.raw.brierInterval95.every((value:number)=>Number.isFinite(value)&&value>=0&&value<=1)).toBe(true);
  expect(report.byCategory.gameWinner.n).toBe(8);expect(report.byModelVersion['SYNTH-MODEL-V7'].n).toBe(8);expect(Object.keys(report.byDate)).toHaveLength(8);expect(report.windows.days7.raw).toBeNull();expect(report.windows.days30.raw).toBeNull();expect(report.windows.allTime.n).toBe(8);expect(report.calibratedProbabilitiesAvailable).toBe(false);expect(state.writes).toHaveLength(0);
 });
 it('does not scan history or fetch sources while loading an interactive pending/stale aggregate',async()=>{
  const lab=await import('../lib/player-props/game-performance');expect(await lab.getGameMarketPerformance()).toMatchObject({status:'pending',sampleSize:null,overall:null});expect(state.queries).toHaveLength(0);expect(state.sourceCalls).toBe(0);expect(state.writes).toHaveLength(0);
  state.cache.set('performance:game-markets-v7',{data:{sampleSize:17,updatedAt:'2026-10-20T00:00:00Z',overall:{raw:{brier:.2}}},expires_at:'2026-10-29T00:00:00Z'});
  expect(await lab.getGameMarketPerformance()).toMatchObject({status:'stale',sampleSize:17,updatedAt:'2026-10-20T00:00:00Z'});expect(state.queries).toHaveLength(0);
 });
 it('appends exact final-score resolutions, preserves forecasts and is idempotent across background refreshes',async()=>{
  state.predictions=[prediction()];const frozen=JSON.stringify(state.predictions),lab=await import('../lib/player-props/game-performance');
  const first=await lab.refreshGameMarketAudit();expect(first).toMatchObject({status:'completed',researchResolutionsAppended:1,personalWagersSettled:0,modelsPromoted:0});expect(first.performance.overall.raw.brier).toBeCloseTo(.36);expect(first.performance.sampleSize).toBe(1);
  expect(state.writes[0].action).toBe('resolutions_put');expect(state.resolutions[0].data).toMatchObject({outcomeBasis:'selected_side_full_payout',exchangeSettlementVerified:false,gameId:'2026_01_BAL_BUF',selectedSide:'YES'});
  const next=await lab.refreshGameMarketAudit();expect(next.researchResolutionsAppended).toBe(0);expect(state.resolutions).toHaveLength(1);expect(JSON.stringify(state.predictions)).toBe(frozen);
  expect(state.queries.every(query=>['shared_prop_snapshots','shared_prop_resolutions'].includes(query.table))).toBe(true);expect(state.queries[0].columns).toContain('captured_quote:shared_prop_quotes');
  expect(await lab.getGameMarketPerformance()).toMatchObject({status:'research_only',sampleSize:1});
 });
 it('adds a correction chain on changed actual scores without rewriting the original prediction or resolution',async()=>{
  state.predictions=[prediction()];const lab=await import('../lib/player-props/game-performance');await lab.refreshGameMarketAudit();const first=structuredClone(state.resolutions[0]);
  state.schedule=state.schedule.replace('BUF,BAL,24,17,','BUF,BAL,17,24,');const next=await lab.refreshGameMarketAudit();expect(next.researchResolutionsAppended).toBe(1);expect(state.resolutions).toHaveLength(2);expect(state.resolutions[0]).toEqual(first);expect(state.resolutions[1].previous_resolution_id).toBe(first.id);expect(next.performance.overall.raw.observedRate).toBe(0);
 });
 it('hydrates a frozen compact quote instead of using current market prices and leaves future games unresolved',async()=>{
  const row=prediction(),{contract:captured,...rest}=row;state.predictions=[{...rest,contract:null,captured_quote:{data:captured},contract_overlay:{observedAt:captured.observedAt}}];
  const lab=await import('../lib/player-props/game-performance'),result=await lab.refreshGameMarketAudit();expect(result.researchResolutionsAppended).toBe(1);expect(result.performance.sampleSize).toBe(1);
  state.predictions=[prediction({event_start:'2026-11-01T18:00:00Z',contract:{...contract(),eventStart:'2026-11-01T18:00:00Z'}})];state.resolutions=[];state.sourceCalls=0;const future=await lab.refreshGameMarketAudit();expect(future).toMatchObject({researchResolutionsAppended:0,performance:{status:'insufficient_evidence',totalSnapshots:1,sampleSize:0}});expect(state.sourceCalls).toBe(0);
 });
 it('fails closed on unavailable or incomplete archive/source coverage without caching invented zero accuracy',async()=>{
  state.archiveError=true;const lab=await import('../lib/player-props/game-performance');expect(await lab.refreshGameMarketAudit()).toMatchObject({status:'failed',researchResolutionsAppended:null});expect(state.cache.size).toBe(0);expect(state.writes).toHaveLength(0);
  state.archiveError=false;state.predictions=[prediction()];state.declaredCount=50001;expect(await lab.refreshGameMarketAudit()).toMatchObject({status:'failed'});expect(state.cache.size).toBe(0);
  state.declaredCount=null;state.sourceError=true;expect(await lab.refreshGameMarketAudit()).toMatchObject({status:'failed'});expect(state.cache.size).toBe(0);expect(state.writes).toHaveLength(0);
 });
});
