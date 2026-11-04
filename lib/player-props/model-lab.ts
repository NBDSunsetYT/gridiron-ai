/** Public football-only reconciliation and controlled calibration jobs.
 * Financial ledgers and private conversations are never read or written here.
 */
import {promisify} from 'node:util';
import {gunzip as gunzipCallback} from 'node:zlib';
import {cloudClient} from '../cloud/context';
import {ApiError} from '../auth';
import {parseWarehouseCSV,NFLVERSE_GAMES} from '../warehouse';
import {boundedFetch,normalizePublicSchedule,NFLVERSE_RELEASE,sha} from '../public-nfl/sources';
import {sharedCache,putCache,fresh} from '../public-nfl/store';
import {allPropPredictions,allPropResolutions,propWrite} from './store';
import {canonicalPropTeam} from './normalize';
import {valueProp} from './math';
import {evaluatePropHistory,scorePropObservations,resolvePropOutcome,fitPropCalibrator,validatePropCandidate,approvePropCalibrator,applyPropCalibration,propModelDrift,PROP_EVALUATION_PROTOCOL,PROP_CALIBRATION_MINIMUMS,type FrozenPropPrediction,type VerifiedPropResolution,type PropCalibrator} from './evaluation';
import type {PropMarketContract} from './market-types';
import {PROP_STATS} from './market-types';
import type {PublicGame} from '../public-nfl/types';

const gunzip=promisify(gunzipCallback),CACHE_KEY='player-props-v6',TTL=15*60000;
type Row=Record<string,any>;
let memory:{expiresAt:number;data:Row}|undefined,pending:Promise<Row>|undefined;
const number=(value:unknown)=>value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value))?Number(value):null;
const iso=(value:unknown)=>typeof value==='string'&&Number.isFinite(Date.parse(value))?new Date(value).toISOString():null;

/** Adapter retains the database's actual archive time. Backdating a JSON
 * capture field cannot turn a post-event row into a prospective forecast. */
export function frozenPropPrediction(row:Row):FrozenPropPrediction{
 const contract=row.contract??row.data?.contract??{},probability=row.probability??row.data?.probability??{};
 const captured=iso(row.captured_at??row.data?.capturedAt)??'';
 const sources=Array.isArray(row.sources)?row.sources:Array.isArray(row.data?.sources)?row.data.sources:[];
 const checked=sources.map((s:Row)=>iso(s.collectedAt??s.checkedAt)).filter(Boolean) as string[];
 const dataAvailableAt=checked.reduce((at,value)=>Date.parse(value)>Date.parse(at)?value:at,captured);
 let marketProbability:number|null=null;
 try{marketProbability=valueProp(contract as PropMarketContract,row.side??row.data?.side??'YES',.5).breakEven;}catch{/* Missing/corrupt cost terms remain unavailable. */}
 return{id:row.id,contractId:contract.id??contract.contractId??row.contract_id??'',gameId:row.game_id??row.data?.game?.id??'',playerId:row.player_id??contract.playerId??'',category:row.category??contract.stat??'',threshold:number(row.threshold??contract.threshold)??NaN,operator:row.operator??contract.operator,side:row.side??row.data?.side??'YES',rawProbability:number(row.raw_probability??probability.raw)??NaN,calibratedProbability:number(row.calibrated_probability??probability.calibrated),calibrationArtifactId:probability.calibrationArtifactId??null,marketProbability,modelVersion:row.model_version??row.data?.modelVersion??'',inputVersion:row.input_version??row.data?.inputVersion??'',rulesHash:contract.rulesHash,predictedAt:captured,eventStart:iso(row.event_start??row.data?.game?.startTime)??'',dataAvailableAt,archivedAt:iso(row.created_at)??'',retrospective:row.data?.retrospective===true};
}
export function frozenPropResolution(row:Row):VerifiedPropResolution{
 const data=row.data??row;
 return{id:row.id??data.id,predictionId:row.prediction_id??data.predictionId,status:row.status??data.status,resolvedAt:iso(row.resolved_at??data.resolvedAt)??'',availableAt:iso(row.available_at??data.availableAt??row.resolved_at??data.resolvedAt)??'',sourceUrl:row.source_url??data.sourceUrl??'',sourceVersion:row.source_version??data.sourceVersion??'',verifiedFinal:row.verified_final??data.verifiedFinal??false,previousResolutionId:row.previous_resolution_id??data.previousResolutionId??null,rulesHash:data.rulesHash,observedValue:number(row.observed_value??data.observedValue)};
}
function aggregate(predictions:FrozenPropPrediction[],resolutions:VerifiedPropResolution[],now=new Date()){
 const report=evaluatePropHistory(predictions,resolutions,now),{rows,exclusions,...summary}=report;
 const grouped=new Map<string,typeof rows>();for(const row of rows){const key=row.category+'|'+row.modelVersion,list=grouped.get(key)??[];list.push(row);grouped.set(key,list);}
 return{...summary,status:report.eligibleResolved?'research_only':'insufficient_evidence',sampleSize:report.eligibleResolved,calibratedSampleSize:report.overall.calibrated?.n??0,updatedAt:now.toISOString(),snapshotCountScope:'mature_events_only',maturationHours:6,scope:'Prospective archived player-contract research whose kickoff preceded this evaluation by at least six hours; separate from upcoming predictions, the historical home-win benchmark and personal wagering performance.',message:report.eligibleResolved?'Final binary statistics are scored without rewriting frozen probabilities. Calibration still requires a matching approved prospective holdout artifact.':'Insufficient prospective settled player-contract evidence. Upcoming forecasts are not historical observations. Calibration, Brier scores and market superiority are not invented.',minimums:PROP_CALIBRATION_MINIMUMS,drift:Object.fromEntries([...grouped].map(([key,group])=>[key,propModelDrift(group)]))};
}
async function readArchive(){
 const[allPredictions,allResolutions]=await Promise.all([allPropPredictions(),allPropResolutions()]);
 // Game/team outcomes have their own final-score auditor. A nullable player
 // identity must never enter player participation checks or calibrator fitting.
 const predictions=(allPredictions as Row[]).filter(row=>(PROP_STATS as readonly string[]).includes(row.category??row.contract?.stat??row.data?.contract?.stat)&&Date.parse(row.event_start??row.data?.game?.startTime)<=Date.now()-6*3600000);
 const ids=new Set(predictions.map(row=>row.id)),resolutions=(allResolutions as Row[]).filter(row=>ids.has(row.prediction_id??row.predictionId??row.data?.predictionId));
 return{rawPredictions:predictions,rawResolutions:resolutions,predictions:predictions.map(frozenPropPrediction),resolutions:resolutions.map(frozenPropResolution)};
}
async function cachePerformance(value:Row){memory={data:value,expiresAt:Date.now()+TTL};await putCache('performance',CACHE_KEY,value,sha(value),TTL).catch(()=>{});return value;}
export async function getPropPerformance(force=false):Promise<Row>{
 if(!force&&memory&&memory.expiresAt>Date.now())return memory.data;
 if(pending)return pending;
 pending=(async()=>{let saved:Awaited<ReturnType<typeof sharedCache>>=null;try{
  saved=await sharedCache('performance',CACHE_KEY);
  if(!force&&fresh(saved)){memory={data:saved!.data,expiresAt:Date.now()+Math.min(TTL,Date.parse(saved!.expires_at!)-Date.now())};return saved!.data;}
  if(!force){
   // Opening a market screen must not page through the complete prospective
   // archive. Scheduled reconciliation computes metrics, while the interactive
   // API reads only this bounded aggregate. Old metrics retain their timestamp.
   const value=saved?.data?{...saved.data,status:'stale',message:'The latest historical evaluation is being refreshed in the background. These saved metrics retain their original evaluation time.'}:{status:'pending',sampleSize:null,eligibleResolved:null,overall:null,updatedAt:null,protocol:PROP_EVALUATION_PROTOCOL,message:'Historical evaluation is pending the scheduled research audit. No model accuracy or calibration was invented.'};
   memory={data:value,expiresAt:Date.now()+60000};return value;
  }
  const archive=await readArchive();return await cachePerformance(aggregate(archive.predictions,archive.resolutions));
 }catch{
  if(saved?.data)return{...saved.data,status:'stale',message:'Current archive coverage could not be verified. Previously calculated historical metrics remain saved; no capped subset was substituted.'};
  return{status:'unavailable',sampleSize:null,eligibleResolved:null,overall:null,updatedAt:null,message:'The complete prospective player-contract archive is temporarily unavailable. No model accuracy or calibration was invented.',protocol:PROP_EVALUATION_PROTOCOL};
 }finally{pending=undefined;}})();return pending;
}

async function modelRows():Promise<Row[]>{
 const response=await cloudClient().from('shared_prop_model_artifacts').select('*',{count:'exact'}).order('created_at',{ascending:false}).limit(2000);
 if(response.error||response.count!==(response.data??[]).length)throw new ApiError('Complete model artifact history could not be verified.',503);
 return response.data??[];
}
function modelSelectionOverrides():Record<string,string|null>{
 const raw=process.env.GRIDIRON_PROP_CALIBRATOR_SELECTION;if(!raw)return{};
 try{const parsed=JSON.parse(raw);if(!parsed||typeof parsed!=='object'||Array.isArray(parsed)||Object.entries(parsed).some(([key,value])=>!key.includes('|')||value!==null&&typeof value!=='string'))throw Error();return parsed;}catch{throw new ApiError('The operator model rollback selection is invalid; calibration is withheld.',503);}
}
/** Operator rollback selects an existing approved artifact, or null to disable
 * calibration for one scope. It never deletes or rewrites model history. */
export function selectApprovedPropCalibrators(models:Row[],overrides:Record<string,string|null>={},now=new Date().toISOString()):Map<string,PropCalibrator>{
 const approved=new Map<string,PropCalibrator>(),selected=[...models].sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at));
 for(const row of selected){if(row.status!=='approved')continue;const artifact=row.data as PropCalibrator,key=artifact.category+'|'+artifact.modelVersion;
  if(!(PROP_STATS as readonly string[]).includes(artifact.category))continue;
  if(Object.prototype.hasOwnProperty.call(overrides,key)&&(overrides[key]===null||overrides[key]!==artifact.id))continue;
  const midpoint=(artifact.minimumRawProbability+artifact.maximumRawProbability)/2;
  if(!approved.has(key)&&applyPropCalibration(midpoint,artifact,{category:artifact.category,modelVersion:artifact.modelVersion,predictedAt:now})!==null)approved.set(key,artifact);
 }
 for(const[key,id]of Object.entries(overrides))if(id!==null&&!approved.has(key))throw new ApiError('The selected rollback artifact is unavailable or does not match its approved model scope; calibration is withheld.',503);
 return approved;
}
export async function loadApprovedPropCalibrators():Promise<Map<string,PropCalibrator>>{
 return selectApprovedPropCalibrators(await modelRows(),modelSelectionOverrides());
}
export const getApprovedPropCalibrators=loadApprovedPropCalibrators;

// Total touchdowns are withheld here: summing defensive and fumble-recovery
// aggregates can double-count the same score. Dedicated verified scorer data
// is required for that contract, just as it is for the simulation's coverage.
const STAT_COLUMNS:Record<string,string[]>={passingYards:['passing_yards'],passingTouchdowns:['passing_tds'],passingAttempts:['attempts'],completions:['completions'],interceptions:['passing_interceptions'],rushingYards:['rushing_yards'],carries:['carries'],receivingYards:['receiving_yards'],receptions:['receptions'],rushingTouchdowns:['rushing_tds'],receivingTouchdowns:['receiving_tds'],targets:['targets']};
export function finalPropStatistic(row:Row,stat:string):number|null{const columns=STAT_COLUMNS[stat];if(!columns)return null;const values=columns.map(column=>number(row[column]));return values.some(value=>value===null)?null:values.reduce<number>((sum,value)=>sum+value!,0);}
export function verifiedPlayerParticipation(row:Row,positiveSnapEvidence:true|null=null):true|null{return positiveSnapEvidence===true||['attempts','carries','targets','punt_returns','kickoff_returns','fg_att','pat_att','pt_att'].some(column=>(number(row[column])??0)>0)?true:null;}

/** Independent participation check, including no-touch players. The GSIS/PFR
 * bridge must be exact and unique; no missing snap row means zero or inactive. */
export function independentSnapParticipation(rosters:Row[],snaps:Row[],prediction:FrozenPropPrediction,contract:PropMarketContract,game:PublicGame):true|null{
 const matches=rosters.filter(row=>row.gsis_id===prediction.playerId&&Number(row.season)===game.season&&canonicalPropTeam(row.team)===canonicalPropTeam(contract.team)&&Number(row.week)>0&&Number(row.week)<=game.week);
 const lastWeek=matches.length?Math.max(...matches.map(row=>Number(row.week))):null;
 const ids=[...new Set(matches.filter(row=>Number(row.week)===lastWeek).map(row=>row.pfr_id).filter((id:unknown)=>typeof id==='string'&&id.length>0))];
 if(ids.length!==1)return null;
 const rows=snaps.filter(row=>row.pfr_player_id===ids[0]&&row.game_id===game.id&&Number(row.season)===game.season&&canonicalPropTeam(row.team)===canonicalPropTeam(contract.team)&&(!row.opponent||canonicalPropTeam(row.opponent)===canonicalPropTeam(contract.opponent)));
 return rows.length===1&&['offense_snaps','defense_snaps','st_snaps'].some(column=>(number(rows[0][column])??0)>0)?true:null;
}

type StatAsset={rows:Row[];version:string;url:string;checkedAt:string};
const statAssets=new Map<number,{expiresAt:number;asset:StatAsset}>();
const participationCache=new Map<number,{expiresAt:number;rosters:StatAsset|null;snaps:StatAsset|null}>();
async function participationAssets(season:number){
 const cached=participationCache.get(season);if(cached&&cached.expiresAt>Date.now())return cached;
 const read=async(tag:string,prefix:string,columns:string[])=>{try{const url=`${NFLVERSE_RELEASE}/${tag}/${prefix}_${season}.csv.gz`,result=await boundedFetch(url,6_000_000,15000),raw=await gunzip(result.body,{maxOutputLength:45_000_000}),rows=parseWarehouseCSV(raw.toString('utf8'));if(!rows.length||!columns.every(column=>column in rows[0]))return null;return{rows,version:sha(result.body),url,checkedAt:new Date().toISOString()};}catch{return null;}};
 const[rosters,snaps]=await Promise.all([read('rosters','roster',['gsis_id','pfr_id','team','season','week']),read('snap_counts','snap_counts',['pfr_player_id','game_id','team','season','offense_snaps','defense_snaps','st_snaps'])]);
 const value={expiresAt:Date.now()+TTL,rosters,snaps};participationCache.set(season,value);return value;
}
export async function finalStatAsset(season:number):Promise<StatAsset>{
 const cached=statAssets.get(season);if(cached&&cached.expiresAt>Date.now())return cached.asset;
 if(!Number.isSafeInteger(season)||season<1999||season>new Date().getUTCFullYear()+1)throw new ApiError('Unsupported final-statistic season.');
 const url=`${NFLVERSE_RELEASE}/stats_player/stats_player_week_${season}.csv.gz`,result=await boundedFetch(url,12_000_000,15000),raw=await gunzip(result.body,{maxOutputLength:45_000_000}),rows=parseWarehouseCSV(raw.toString('utf8'));
 if(!rows.length||!['player_id','season','season_type','week','team','game_id'].every(column=>column in rows[0]))throw new ApiError('Published final-player-statistic identity fields are unavailable.',502);
 const asset={rows,version:sha(result.body),url,checkedAt:new Date().toISOString()};statAssets.set(season,{expiresAt:Date.now()+TTL,asset});return asset;
}
/** Exact GSIS, game ID, team, season, week and opponent matching. A missing
 * stat row or all-zero opportunities does not prove non-participation. */
export function matchFinalPlayerRow(rows:Row[],prediction:FrozenPropPrediction,contract:PropMarketContract,game:PublicGame):Row|null{
 const matches=rows.filter(row=>row.player_id===prediction.playerId&&row.game_id===game.id&&Number(row.season)===game.season&&Number(row.week)===game.week&&row.season_type===(game.week>18?'POST':'REG')&&canonicalPropTeam(row.team)===canonicalPropTeam(contract.team)&&(!row.opponent_team||canonicalPropTeam(row.opponent_team)===canonicalPropTeam(contract.opponent)));
 return matches.length===1?matches[0]:null;
}
async function reconcile(archive:Awaited<ReturnType<typeof readArchive>>){
 const now=Date.now(),past=archive.predictions.filter(prediction=>Date.parse(prediction.eventStart)<now),updates:Row[]=[],notes:string[]=[];
 if(!past.length)return{updates,notes};
 const seasons=[...new Set(past.map(prediction=>Number(prediction.gameId.slice(0,4))))];if(seasons.length>5)throw new ApiError('Partition more than five final-statistic seasons explicitly before reconciliation.',413);
 const scheduleSource=await boundedFetch(NFLVERSE_GAMES),scheduleText=scheduleSource.body.toString('utf8'),checkedAt=new Date().toISOString(),games=new Map<string,PublicGame>();
 for(const season of seasons)for(const game of normalizePublicSchedule(scheduleText,checkedAt,season).games)games.set(game.id,game);
 const originals=new Map(archive.rawPredictions.map(row=>[row.id,row])),latest=new Map<string,VerifiedPropResolution>();
 for(const resolution of archive.resolutions){const old=latest.get(resolution.predictionId);if(!old||Date.parse(resolution.resolvedAt)>Date.parse(old.resolvedAt))latest.set(resolution.predictionId,resolution);}
 const assets=new Map<number,StatAsset>(),participation=new Map<number,Awaited<ReturnType<typeof participationAssets>>>();for(const season of seasons){try{assets.set(season,await finalStatAsset(season));participation.set(season,await participationAssets(season));}catch{notes.push(`Final player statistics for ${season} are unavailable; matching outcomes remain unresolved.`);}}
 for(const prediction of past){
  const game=games.get(prediction.gameId),original=originals.get(prediction.id),contract=original?.contract as PropMarketContract|undefined;
  if(!game||game.status!=='final'||!contract)continue;
  const asset=assets.get(game.season);if(!asset)continue;const row=matchFinalPlayerRow(asset.rows,prediction,contract,game);if(!row)continue;
  const part=participation.get(game.season),positiveSnap=independentSnapParticipation(part?.rosters?.rows??[],part?.snaps?.rows??[],prediction,contract,game),played=verifiedPlayerParticipation(row,positiveSnap);
  const sourceVersion=sha({statistics:asset.version,roster:part?.rosters?.version??null,snaps:part?.snaps?.version??null}),availableAt=[asset.checkedAt,part?.rosters?.checkedAt,part?.snaps?.checkedAt].filter((value):value is string=>Boolean(value)).sort().at(-1)!;
  const outcome=resolvePropOutcome({gameId:game.id,playerId:prediction.playerId,category:prediction.category,threshold:prediction.threshold,operator:prediction.operator,rulesVerified:contract.settlement.rulesVerified,fullGame:contract.settlement.fullGame,includesOvertime:contract.settlement.overtimeIncluded,dnpRule:contract.settlement.nonParticipationPolicy==='void'?'void':contract.settlement.nonParticipationPolicy==='stat_zero'?'settle_zero':'unverified',rulesHash:contract.rulesHash},{gameId:game.id,playerId:prediction.playerId,category:prediction.category,value:finalPropStatistic(row,prediction.category),gameFinal:true,fullGame:true,includesOvertime:true,participated:played,checkedAt:availableAt,sourceUrl:asset.url,sourceVersion,verified:true});
  const previous=latest.get(prediction.id),verifiedFinal=outcome.status==='yes'||outcome.status==='no'||outcome.status==='void';
  if(previous&&previous.status===outcome.status&&previous.observedValue===outcome.observedValue&&previous.verifiedFinal===verifiedFinal)continue;
  if(previous?.sourceVersion===sourceVersion)continue; // No fabricated source revision.
  const resolution={id:'prop-resolution-'+sha([prediction.id,outcome.status,outcome.observedValue,sourceVersion,previous?.id??null]),predictionId:prediction.id,status:outcome.status,observedValue:outcome.observedValue,resolvedAt:new Date().toISOString(),availableAt,sourceUrl:asset.url,sourceVersion,verifiedFinal,previousResolutionId:previous?.id??null,rulesHash:contract.rulesHash,evidence:{method:'exact published full-game statistic compared with frozen contract',participation:positiveSnap?'Positive offense, defense or special-teams snaps through an exact GSIS/PFR mapping':played?'Positive source opportunity/return/kicking activity':'Participation unknown',participationSources:[part?.rosters&&{url:part.rosters.url,version:part.rosters.version},part?.snaps&&{url:part.snaps.url,version:part.snaps.version}].filter(Boolean),exchangeSettlementVerified:false,sourceMeaning:'nflverse published league-derived game statistics; no private wager is settled',reason:outcome.reason}};
  updates.push(resolution);
 }
 for(let offset=0;offset<updates.length;offset+=500)await propWrite({action:'resolutions_put',resolutions:updates.slice(offset,offset+500)});
 return{updates,notes};
}

/** Retraining cadence is data-driven and separate from promotion. One wrong
 * forecast never triggers a replacement model or a personal ledger write. */
export async function refreshPropModelLab(){
 const archive=await readArchive(),reconciliation=await reconcile(archive);
 const current=reconciliation.updates.length?await readArchive():archive,models=await modelRows(),activeModels=selectApprovedPropCalibrators(models,modelSelectionOverrides()),scored=scorePropObservations(current.predictions,current.resolutions),groups=new Map<string,typeof scored.rows>();
 for(const row of scored.rows){const key=row.category+'|'+row.modelVersion,group=groups.get(key)??[];group.push(row);groups.set(key,group);}
 const candidates:string[]=[],approved:string[]=[],reviews:Row[]=[];
 for(const[key,rows]of groups){
  const[category,modelVersion]=key.split('|'),related=models.filter(model=>model.category===category&&model.model_version===modelVersion),pendingCandidate=related.find(model=>model.status==='candidate'&&!related.some(other=>other.id===model.id&&other.status==='approved'));
  if(pendingCandidate){
   const candidate=pendingCandidate.data as PropCalibrator,incumbent=activeModels.get(key)??null;
   try{
    const validation=validatePropCandidate(candidate,current.predictions,current.resolutions,new Date(),incumbent);
    reviews.push({candidateId:candidate.id,eligibleForPromotion:validation.eligibleForPromotion,n:validation.n,games:validation.games,reasons:validation.reasons,incumbentId:validation.incumbentId,validationHash:validation.validationHash});
    if(validation.eligibleForPromotion){const artifact=approvePropCalibrator(candidate,validation);await propWrite({action:'model_artifact_put',artifact});approved.push(artifact.id);continue;}
    // Failed fixed holdouts cannot be enlarged until they happen to pass.
    // A later fit gets new training data, a new archived identity and entirely
    // subsequent holdout games; the rejected artifact remains preserved.
    if(validation.games<candidate.validationGameTarget||validation.n<PROP_CALIBRATION_MINIMUMS.validationPredictions)continue;
   }catch(error){reviews.push({candidateId:candidate.id,status:'withheld',message:error instanceof Error?error.message:'Candidate validation was withheld.'});continue;}
  }
  const latestModel=related[0],previousIds=new Set<string>(latestModel?.data?.trainingSnapshotIds??[]),newRows=rows.filter(row=>!previousIds.has(row.predictionId));
  if(rows.length<PROP_CALIBRATION_MINIMUMS.trainingPredictions||new Set(rows.map(row=>row.gameId)).size<PROP_CALIBRATION_MINIMUMS.trainingGames)continue;
  if(latestModel&&(newRows.length<200||new Set(newRows.map(row=>row.gameId)).size<40||Date.now()-Date.parse(latestModel.created_at)<7*86400000))continue;
  try{const artifact=fitPropCalibrator(current.predictions,current.resolutions,{category,modelVersion,asOf:new Date().toISOString(),method:'isotonic'});await propWrite({action:'model_artifact_put',artifact});candidates.push(artifact.id);}catch(error){reviews.push({category,modelVersion,status:'insufficient_evidence',message:error instanceof Error?error.message:'Candidate fit was withheld.'});}
 }
 const performance=await cachePerformance(aggregate(current.predictions,current.resolutions));
 return{status:'completed',checkedAt:new Date().toISOString(),researchResolutionsAppended:reconciliation.updates.length,candidatesCreated:candidates,modelsApproved:approved,reviews,notes:reconciliation.notes,performance,personalWagersSettled:0};
}
