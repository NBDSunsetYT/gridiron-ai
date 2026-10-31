/** Supplementary NFL sportsbook references. Never a DraftKings Predictions feed
 * and never an automatic personal wager or ledger operation. */
import {randomUUID} from 'node:crypto';
import {after} from 'next/server';
import {ApiError} from '../auth';
import {loadSchedule,trustedGame,PUBLIC_PIPELINE_VERSION} from '../public-nfl/service';
import {sha} from '../public-nfl/sources';
import {sharedJob,latestJobs} from '../public-nfl/store';
import {cachedGameStates} from '../player-props/store';
import {canonicalPropName,canonicalPropTeam} from '../player-props/normalize';
import {exactPropDistribution,thresholdHit} from '../player-props/math';
import {wilson} from '../model';
import {footballStorage,persistProviderQuotes} from '../college-football/store';
import type {ProviderQuote} from '../college-football/types';
import type {PublicGame} from '../public-nfl/types';
import {readNflSportsData,sportsDataBridgeConfiguration,bridgeDiagnostic,BDL_NFL_DOCS} from './bridge';
import type {SportsbookReferenceDashboard,SportsbookReference,BdlResponse,ReferenceDiagnostic,SportsbookReferenceFilters} from './types';
const maxMemory=12_000_000;
let snapshot:SportsbookReferenceDashboard|null=null,pending:Promise<void>|null=null;
const stats:Record<string,string>={passing_yards:'passingYards',passing_tds:'passingTouchdowns',passing_attempts:'passingAttempts',passing_completions:'completions',passing_interceptions:'interceptions',rushing_yards:'rushingYards',rushing_attempts:'carries',receiving_yards:'receivingYards',receptions:'receptions'};
const safe=async<T>(work:()=>Promise<T>,fallback:T)=>{try{return await work();}catch{return fallback;}};
function empty(problem:ReferenceDiagnostic,games:PublicGame[]=[]):SportsbookReferenceDashboard{const at=new Date().toISOString();return{provider:'BALLDONTLIE',sport:'NFL',dataFamily:'sportsbook_reference',status:'unavailable',runId:null,checkedAt:at,updatedAt:at,games,gameId:null,items:[],results:[],totalResults:0,diagnostic:problem,sources:[],progress:{phase:problem.message,completed:0,total:4},persistence:{saved:false,status:'not_saved',count:0,message:'No new provider research has been saved.'},limitations:['BALLDONTLIE DraftKings vendor data is DraftKings Sportsbook reference odds, not DraftKings Predictions event-contract prices.','Source updated_at is provider refresh time; quotedAt and executable-offer verification are unavailable.','Missing identities, settlement rules, transaction costs and probabilities remain unavailable.'],sourceChecks:[]};}
function future(games:PublicGame[]){return games.filter(g=>g.status!=='final'&&Date.parse(g.startTime)>Date.now()&&Date.parse(g.startTime)<Date.now()+7*86400000);}
export async function sportsbookReferenceDashboard(filter:SportsbookReferenceFilters={}):Promise<SportsbookReferenceDashboard>{
 if(filter.scope!==undefined&&!['all','player','game'].includes(filter.scope))throw new ApiError('Choose all, player or game sportsbook references.');
 const problem=sportsDataBridgeConfiguration(),schedule=await safe<Awaited<ReturnType<typeof loadSchedule>>|null>(()=>loadSchedule(),null),games=future(schedule?.games??[]);if(problem)return empty(problem,games);
 if(!snapshot)return empty(bridgeDiagnostic('provider_not_checked','The Render data bridge is configured, but no verified NFL sportsbook reference refresh has completed. No API entitlement is assumed.'),games);
 const offset=filter.cursor??0,limit=filter.limit??60;if(!Number.isSafeInteger(offset)||offset<0||offset>30000||!Number.isInteger(limit)||limit<1||limit>80)throw new ApiError('Choose a bounded sportsbook reference page.');
 const matching=snapshot.items.filter(row=>(!filter.scope||filter.scope==='all'||(filter.scope==='player'?Boolean(row.player):!row.player))&&(!filter.vendor||row.book.key===filter.vendor)&&(!filter.statistic||row.market.statistic===filter.statistic)),page=matching.slice(offset,offset+limit),current={...snapshot,items:page,results:page,totalResults:matching.length,nextCursor:offset+page.length<matching.length?String(offset+page.length):null,games};if(['available','partial'].includes(current.status)&&Date.now()-Date.parse(current.updatedAt)>120000)return{...current,status:'partial',diagnostic:bridgeDiagnostic('cached_reference','These are cached sportsbook references. Provider refresh time is shown; current executable prices are not verified.')};return current;
}
export function mapBdlGame(game:PublicGame,records:Record<string,any>[]){const matches=records.filter(row=>Number.isInteger(row.id)&&row.id>0&&row.season===game.season&&row.week===game.week&&canonicalPropTeam(row.home_team?.abbreviation??'')===canonicalPropTeam(game.home.id)&&canonicalPropTeam(row.visitor_team?.abbreviation??'')===canonicalPropTeam(game.away.id)&&Number.isFinite(Date.parse(row.date))&&Date.parse(row.date)===Date.parse(game.startTime));return matches.length===1?matches[0]:null;}
export function mapBdlPlayer(player:Record<string,any>|undefined,catalog:Record<string,any>[],game:PublicGame){
 if(!player||typeof player.first_name!=='string'||typeof player.last_name!=='string')return null;
 const name=player.first_name+' '+player.last_name,team=canonicalPropTeam(player.team?.abbreviation??'');if(![canonicalPropTeam(game.home.id),canonicalPropTeam(game.away.id)].includes(team))return null;
 const matches=catalog.filter(p=>/^00-\d{7}$/.test(p.id??'')&&canonicalPropTeam(p.team??'')===team&&[p.name,...Array.isArray(p.aliases)?p.aliases:[]].some((n:string)=>typeof n==='string'&&canonicalPropName(n)===canonicalPropName(name)));return matches.length===1?{id:matches[0].id,name,team}:null;
}
async function existingModel(game:PublicGame){const states=await cachedGameStates([game.id]),state=states.get(game.id);if(!state||state.pipeline!==PUBLIC_PIPELINE_VERSION||!(state.verified===true||state.verified==='true')||Date.now()-Date.parse(state.updated_at)>30*60000)return null;const jobs=await latestJobs(10,[state.input_hash]),job=jobs.find(j=>j.game_id===game.id&&j.status==='completed'&&j.input_hash===state.input_hash);if(!job)return null;const full=await sharedJob(job.id),result=full?.result?.result;if(!result||!Number.isInteger(result.simulations)||result.simulations<10000||result.simulations>100000||canonicalPropTeam(result.home)!==canonicalPropTeam(game.home.id)||canonicalPropTeam(result.away)!==canonicalPropTeam(game.away.id)||Date.parse(result.eventStart)!==Date.parse(game.startTime))return null;return full;}
export function attachStatisticalReference(row:SportsbookReference,job:any):SportsbookReference{
 const result=job?.result?.result;if(!row.player?.gsisId||!result)return{...row,projection:null,projectionStatus:row.player?.gsisId?'current_verified_simulation_unavailable':'player_identity_unverified'};
 const stat=stats[row.market.statistic];if(row.market.type!=='over_under'||row.market.period!=='unspecified'||!stat)return{...row,projection:null,projectionStatus:'market_period_or_settlement_scope_unverified'};
 const line=Number(row.market.line),distribution=exactPropDistribution(result,row.player.gsisId,stat);if(!Number.isFinite(line)||!distribution)return{...row,projection:null,projectionStatus:'exact_distribution_unavailable'};
 const n=distribution.simulations,hits=(op:string)=>distribution.histogram.filter(r=>thresholdHit(r.value,line,op)).reduce((v,r)=>v+r.count,0),above=hits('gt'),below=hits('lt'),equal=hits('eq');
 return{...row,projectionStatus:'statistical_threshold_reference_only',projection:{simulationId:job.id,modelVersion:result.modelVersion,inputVersion:result.inputDataVersion,simulations:n,statistic:stat,threshold:line,aboveProbability:above/n,belowProbability:below/n,equalProbability:equal/n,monteCarloInterval95:wilson(above,n),calibratedProbability:null,marketHitProbability:null,expectedValue:null,basis:'Full-game simulated statistic including modeled overtime. This is a statistical threshold reference, not a verified sportsbook settlement probability. Participation, period, push and payout rules remain unverified.'}};
}
function checkRow(row:SportsbookReference,game:PublicGame,players:Map<number,any>,job:any){
 const value={...row,nflverseGameId:game.id};if(!value.player)return{...value,projection:null,projectionStatus:'sportsbook_settlement_rules_unverified'};
 const player=players.get(value.player.bdlId),identity=mapBdlPlayer(player,job?.result?.research?.playerCatalog??[],game);
 value.player={...value.player,name:player&&typeof player.first_name==='string'&&typeof player.last_name==='string'?player.first_name+' '+player.last_name:null,team:player?.team?.abbreviation?canonicalPropTeam(player.team.abbreviation):null,gsisId:identity?.id??null,mapping:{status:identity?'verified':'unmapped',method:'exact_current_NFL_roster_name_team_and_game',reason:identity?null:'A unique current GSIS player identity could not be verified. No provider integer ID is treated as GSIS.'}};
 return attachStatisticalReference(value,job);
}
async function persistReferences(rows:SportsbookReference[]){
 if(!rows.length)return{saved:false,status:'not_saved',count:0,message:'No verified references were available to save.'};
 const storage=await footballStorage();if(storage.admissionAvailable!==true)return{saved:false,status:storage.admissionAvailable===false?'paused_capacity':'unavailable',count:0,message:storage.message};
 const quotes:ProviderQuote[]=rows.flatMap(row=>row.outcomes.map(outcome=>({id:sha([row.id,outcome.side]),provider:'BallDontLie' as const,sport:'NFL' as const,marketFamily:'sportsbook_reference' as const,eventId:String(row.gameId),marketId:row.referenceId,selection:outcome.side,line:outcome.line,americanOdds:outcome.americanOdds,observedAt:row.observedAt,quotedAt:null,sourceUrl:row.sourceUrl,data:{...row,projection:null}})));
 let count=0;for(let at=0;at<quotes.length;at+=75){const result=await persistProviderQuotes(quotes.slice(at,at+75));if(!result.saved)return{...result,count};count+=result.count;}return{saved:true,status:'saved',count};
}
async function execute(game:PublicGame,runId:string){
 if(!snapshot||snapshot.runId!==runId)return;const update=(value:Partial<SportsbookReferenceDashboard>)=>{if(snapshot?.runId===runId)snapshot={...snapshot,...value,updatedAt:new Date().toISOString()};};
 const checks:SportsbookReferenceDashboard['sourceChecks']=[],call=async(resource:string,params:Record<string,any>)=>{const response=await readNflSportsData(resource,params);checks.push({resource,status:response.status,diagnostic:response.diagnostic});update({sourceChecks:[...checks]});return response;};
 try{
  update({status:'running',progress:{phase:'Matching the verified NFL game to the provider schedule',completed:0,total:4}});
  const [games,job]=await Promise.all([call('games',{seasons:[game.season],weeks:[game.week],per_page:100}),safe(()=>existingModel(game),null)]);
  if(games.status==='unavailable'){update({status:'unavailable',diagnostic:games.diagnostic,progress:{phase:games.diagnostic.message,completed:1,total:4}});return;}
  const match=mapBdlGame(game,games.records??[]);if(!match){const problem=bridgeDiagnostic(games.complete===false?'game_lookup_incomplete':'game_identity_unverified','The provider game could not be uniquely matched to the exact NFL teams, kickoff and week. No market was assigned to a guessed game.');update({status:'unavailable',diagnostic:problem,progress:{phase:problem.message,completed:1,total:4}});return;}
  update({progress:{phase:'Retrieving sportsbook references without treating them as event contracts',completed:1,total:4}});
  const odds=await call('odds',{game_ids:[match.id],per_page:100});
  update({progress:{phase:'Retrieving supported player-prop reference lines',completed:2,total:4}});
  const props=await call('player-props',{game_id:match.id}),ids=[...new Set((props.items??[]).map(row=>row.player?.bdlId).filter((id):id is number=>Number.isSafeInteger(id)&&Number(id)>0))];
  let playerResponse:BdlResponse|null=null;if(ids.length){update({progress:{phase:'Verifying exact NFL player identities',completed:3,total:4}});playerResponse=await call('players',{player_ids:ids.slice(0,100),per_page:100});}
  const players=new Map((playerResponse?.records??[]).filter(row=>Number.isSafeInteger(row.id)).map(row=>[row.id,row]));
  const all=[...(odds.items??[]),...(props.items??[])].filter(row=>row.gameId===match.id).map(row=>checkRow(row,game,players,job));
  if(Buffer.byteLength(JSON.stringify(all))>maxMemory){const problem=bridgeDiagnostic('reference_memory_bound','The verified reference dataset exceeds this bounded interactive refresh. No partial list is labeled complete.');update({status:'unavailable',items:[],results:[],totalResults:0,diagnostic:problem});return;}
  const persistence=await persistReferences(all),unavailable=checks.find(c=>c.status==='unavailable'),partial=checks.some(c=>c.status!=='available')||ids.length>100;
  const diagnostic=unavailable?.diagnostic??bridgeDiagnostic(all.length?'reference_data_verified':'no_matching_markets',all.length?'Provider sportsbook references were retrieved. Exact executable availability, native event-contract rules and after-fee value remain unverified.':'The provider responded successfully without matching sportsbook references for this NFL game.');
  const sources=checks.map(c=>({id:'bdl-nfl-'+c.resource,name:'BALLDONTLIE NFL '+c.resource,url:BDL_NFL_DOCS,collectedAt:c.diagnostic.checkedAt,publishedAt:null,status:c.status==='available'?'available' as const:'partial' as const}));
  update({status:all.length?(partial?'partial':'available'):'unavailable',items:all,results:all,totalResults:all.length,diagnostic,sources,persistence,progress:{phase:all.length?'NFL sportsbook reference refresh complete; event-contract analysis remains separate':diagnostic.message,completed:4,total:4}});
 }catch{update({status:'unavailable',diagnostic:bridgeDiagnostic('reference_refresh_failed','The NFL reference refresh could not complete. Existing NFL models and personal records are unchanged.',{retryable:true})});}
}
export async function analyzeNflSportsbookReference(input:{gameId?:string}={},filter:SportsbookReferenceFilters={}):Promise<SportsbookReferenceDashboard>{
 if(filter.scope!==undefined&&!['all','player','game'].includes(filter.scope))throw new ApiError('Choose all, player or game sportsbook references.');
 const problem=sportsDataBridgeConfiguration();if(problem)return sportsbookReferenceDashboard(filter);
 const schedule=await loadSchedule(),games=future(schedule.games),game=input.gameId?await trustedGame(input.gameId):games[0];if(!game)return empty(bridgeDiagnostic('no_upcoming_nfl_game','No verified upcoming NFL matchup is currently available.'),games);
 if((pending||snapshot&&['queued','running'].includes(snapshot.status))&&snapshot)return sportsbookReferenceDashboard(filter);
 const runId=randomUUID();snapshot={...empty(bridgeDiagnostic('reference_refresh_queued','A bounded server-side NFL sportsbook reference refresh is queued.'),games),status:'queued',runId,gameId:game.id};
 after(async()=>{if(pending)return;const task=execute(game,runId);pending=task;try{await task;}finally{pending=null;}});return snapshot;
}
export async function refreshNflSportsbookReference(input:{gameId?:string}={}):Promise<SportsbookReferenceDashboard>{if(sportsDataBridgeConfiguration())return sportsbookReferenceDashboard();if(snapshot&&Date.now()-Date.parse(snapshot.updatedAt)<120000)return snapshot;return analyzeNflSportsbookReference(input);}
