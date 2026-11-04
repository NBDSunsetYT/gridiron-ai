import {cloudClient} from '../cloud/context';
import {ApiError} from '../auth';
import {sha} from '../public-nfl/sources';
import type {PropRun,PropResearch} from './types';
import {PROP_STATS,type PropMarketContract} from './market-types';
const client=()=>cloudClient();
function checked<T>({data,error}:{data:T;error:unknown}):T{if(error){const problem=error as {code?:string;message?:string};console.error('Player research storage:',problem.code??'unknown',(problem.message??'Query failed').slice(0,240).replace(/[A-Za-z0-9_-]{40,}/g,'[redacted identifier]'));if(problem.code==='54000'&&/personal.record storage|storage review|storage headroom/i.test(problem.message??''))throw new ApiError('New public research is paused to preserve personal-record storage. Saved research and Wallet remain available; storage capacity needs an operator review.',503);throw new ApiError('Player research storage is temporarily unavailable. Existing records are preserved.',503);}return data;}
export async function propWrite(payload:Record<string,any>):Promise<any>{const token=process.env.GRIDIRON_PUBLIC_INGEST_TOKEN;if(!token||token.length<40)throw new ApiError('Automatic player research is temporarily unavailable.',503);let result:any;for(let attempt=0;attempt<3;attempt++){result=await client().rpc('gridiron_prop_write',{token,payload});if(!result.error||!/(?:upstream|temporary|timeout|fetch|network|connection|gateway|503|rate.limit)/i.test(String(result.error.message))||attempt===2)break;await new Promise(resolve=>setTimeout(resolve,250*(attempt+1)));}return checked(result);}
export async function propBatch(operations:Record<string,any>[]){const results:any[]=[];for(let offset=0;offset<operations.length;offset+=75)results.push(...await propWrite({action:'batch',operations:operations.slice(offset,offset+75)}));return results;}
export async function propRun(id?:string,full=false,metadataOnly=false):Promise<PropRun|null>{let query=client().from('shared_prop_runs').select(full?'*':`id,status,${metadataOnly?'':'result,'}error,lease,created_at,updated_at,previous_run:data->>previousRunId,pipeline:data->>pipelineVersion,selected_provider:data->>provider`).order('created_at',{ascending:false}).limit(1);if(id)query=query.eq('id',id);const row=checked(await query.maybeSingle()) as any;if(row&&!full)row.data={previousRunId:row.previous_run??null,pipelineVersion:row.pipeline??null,provider:row.selected_provider??null};return row as PropRun|null;}
export async function storedContracts(gameId:string):Promise<PropMarketContract[]>{
 const rows:PropMarketContract[]=[];let total:number|null=null;
 for(let offset=0;offset<10000;){const response=await client().from('shared_prop_contracts').select('data',{count:'exact'}).eq('game_id',gameId).order('id').range(offset,offset+499);const page=checked(response)??[];if(total===null)total=response.count??null;else if(total!==response.count)throw new ApiError('Contract coverage changed while loading. Retry to retrieve a complete page.',409);rows.push(...page.map((row:any)=>row.data));offset+=page.length;if(total!==null&&offset>=total)return rows;if(!page.length)break;}
 throw new ApiError('Complete contract coverage exceeds the interactive research bound; no partial list was labeled complete.',413);
}
export function contractDefinitionHash(contract:PropMarketContract){return sha({id:contract.contractId,provider:contract.provider,eventId:contract.eventId,gameId:contract.gameId,eventStart:contract.eventStart,providerPlayerId:contract.providerPlayerId,playerName:contract.playerName,team:contract.team,stat:contract.stat,threshold:contract.threshold,operator:contract.operator,rules:contract.rulesHash});}
export function contractQuoteHash(contract:PropMarketContract){const{openInterest,volume,...sizes}=contract.liquidity;return sha({yesAsk:contract.yesAskCents,noAsk:contract.noAskCents,yesBid:contract.yesBidCents,noBid:contract.noBidCents,last:contract.lastTradedPriceCents,displayedYes:contract.displayedYesPercent??null,displayedNo:contract.displayedNoPercent??null,fees:{...contract.fees,observedAt:undefined},liquidity:sizes});}
export async function storeContracts(contracts:PropMarketContract[]){return propBatch(contracts.map(contract=>{const quoteHash=contractQuoteHash(contract);return{action:'contract_put',contract,definitionHash:contractDefinitionHash(contract),quoteHash,quoteId:sha([contract.id,quoteHash])};}));}
export function researchRank(row:PropResearch){
 // A lexicographic ordering, not a confidence score: verified net value first;
 // otherwise supported evidence, then coverage checks, then sampling width.
 if(row.valuation.netValueCents!==null)return Math.max(0,Math.min(299999999,Math.round((100-Number(row.valuation.netValueCents))*1000000)));
 return(row.probability.raw===null?1000000000:500000000)+(100-row.dataQuality.score)*1000000+Math.round((row.probability.interval95?row.probability.interval95[1]-row.probability.interval95[0]:1)*999999);
}
export async function storeResearch(rows:PropResearch[],quoteIds:Map<string,string>,runId:string){
 const compact=rows.map(compactResearchForWrite);
 return propBatch(compact.map(snapshot=>({action:'snapshot_put',snapshot,quoteId:quoteIds.get(snapshot.contract.id),runId,rank:researchRank(snapshot)})));
}
export function compactResearchForWrite(row:PropResearch){
 const team=(value:PropResearch['game']['home'])=>({id:value.id,name:value.name,abbreviation:value.abbreviation});
 return{...row,storageRequest:'nfl_market_snapshot_v7',game:{id:row.game.id,season:row.game.season,week:row.game.week,startTime:row.game.startTime,status:row.game.status,home:team(row.game.home),away:team(row.game.away),sources:[]},distribution:null,sources:row.sources.filter(s=>/pbp|injur|schedule/.test(s.id)).slice(0,3).map(({id,name,url,collectedAt,publishedAt,status,version})=>({id,name,url,collectedAt,status,...publishedAt?{publishedAt}:{},...version?{version}:{}})),sourceEvidenceRef:{simulationId:row.simulationId,inputVersion:row.inputVersion}};
}
/** V7 removes repeated rules from new snapshots only. The immutable quote FK
 * supplies the exact historical definition; capture-specific overlays retain
 * original identity verification and observation clocks. V6 rows stay intact. */
export function hydrateStoredResearch(data:any,capturedContract?:PropMarketContract):PropResearch{
 if(data?.storageEncoding!=='nfl_market_snapshot_v7')return data as PropResearch;
 if(data.contract)return data as PropResearch;
 if(!capturedContract||typeof data.contractOverlay!=='object')throw new ApiError('The immutable historical contract reference could not be restored.',503);
 return{...data,contract:{...capturedContract,...data.contractOverlay}} as PropResearch;
}
export type PropFilters={category?:string;gameId?:string;side?:'YES'|'NO';search?:string;cursor?:string;limit?:number;minQuality?:number;scope?:'all'|'player'|'game';provider?:'DraftKings Predictions'|'Kalshi';ranking?:'coverage'|'calibrated'|'disagreement'|'reliability'|'uncertainty'|'injury'|'movement'};
export async function researchPage(runId:string,filter:PropFilters={}):Promise<{rows:PropResearch[];total:number;nextCursor:string|null}>{
 const start=Number(filter.cursor??0),limit=Math.min(filter.limit??60,80);if(!Number.isSafeInteger(start)||start<0||start>100000||!Number.isInteger(limit)||limit<1)throw new ApiError('Invalid research page.');
 if(filter.scope||filter.provider||filter.ranking){const response=checked(await client().rpc('gridiron_nfl_research_page',{p_run_id:runId,p_filter:{...filter,cursor:String(start),limit}})) as any;if(!response||!Array.isArray(response.rows)||!Number.isSafeInteger(response.total))throw new ApiError('The complete research page could not be verified.',503);return{rows:response.rows.map((row:any)=>hydrateStoredResearch(row)),total:response.total,nextCursor:response.nextCursor??null};}
 let query=client().from('shared_prop_run_results').select('rank,research:shared_prop_snapshots!inner(*,captured_quote:shared_prop_quotes!shared_prop_snapshots_quote_id_fkey(data))',{count:'exact'}).eq('run_id',runId);
 if(filter.category)query=query.eq('research.category',filter.category);if(filter.gameId)query=query.eq('research.game_id',filter.gameId);if(filter.side)query=query.eq('research.side',filter.side);
 if(filter.search)query=query.ilike('research.player_name','%'+filter.search.replace(/[\\%_]/g,'\\$&')+'%');if(filter.minQuality!==undefined)query=query.gte('research.data_quality_score',filter.minQuality);
 const response=await query.order('rank').order('snapshot_id').range(start,start+limit-1),values=checked(response)??[],total=response.count??0;
 return{rows:values.map((row:any)=>hydrateStoredResearch(row.research.data,row.research.captured_quote?.data)) as PropResearch[],total,nextCursor:start+values.length<total?String(start+values.length):null};
}
export async function storedResearch(id:string):Promise<PropResearch|null>{const row=checked(await client().from('shared_prop_snapshots').select('data,captured_quote:shared_prop_quotes!shared_prop_snapshots_quote_id_fkey(data)').eq('id',id).maybeSingle()) as any;return row?hydrateStoredResearch(row.data,row.captured_quote?.data):null;}
export async function currentContracts(ids:string[]):Promise<Map<string,PropMarketContract>>{const found=new Map<string,PropMarketContract>();for(let offset=0;offset<ids.length;offset+=35){const rows=checked(await client().from('shared_prop_contracts').select('id,data').in('id',ids.slice(offset,offset+35)))??[];for(const row of rows as any[])found.set(row.id,row.data);}return found;}
export async function cachedGameStates(gameIds:string[]){const rows=checked(await client().from('shared_nfl_cache').select('key,input_hash,updated_at,pipeline:data->>pipelineVersion,verified:data->>inputVerified').eq('kind','detail').in('key',[...new Set(gameIds)]))??[];return new Map<string,any>((rows as any[]).map(row=>[row.key,row]));}
export async function allPropPredictions(){
 const rows:any[]=[];let total:number|null=null;
 for(let offset=0;offset<50000;){const response=await client().from('shared_prop_snapshots').select('id,game_id,player_id,category,side,threshold,operator,raw_probability,calibrated_probability,model_version,input_version,captured_at,created_at,event_start,contract:data->contract,contract_overlay:data->contractOverlay,captured_quote:shared_prop_quotes!shared_prop_snapshots_quote_id_fkey(data),probability:data->probability,sources:data->sources',{count:'exact'}).in('category',[...PROP_STATS]).lte('event_start',new Date(Date.now()-6*3600000).toISOString()).not('raw_probability','is',null).order('id').range(offset,offset+499);const page=checked(response)??[];if(total===null)total=response.count??null;else if(total!==response.count)throw new ApiError('The prediction archive changed during evaluation. Retry before calculating a complete historical score.',409);rows.push(...page.map((row:any)=>{const{captured_quote,contract_overlay,...rest}=row;return{...rest,contract:row.contract??{...captured_quote?.data,...contract_overlay}};}));offset+=page.length;if(total!==null&&offset>=total)return rows;if(!page.length)break;}
 throw new ApiError('The complete prediction archive exceeds this interactive report bound. No capped subset was scored as the full model record.',413);
}
export async function allPropResolutions(){const response=await client().from('shared_prop_resolutions').select('*',{count:'exact'}).order('resolved_at').limit(10000),rows=checked(response)??[];if(response.count!==rows.length)throw new ApiError('The complete resolution archive requires a bounded export; no truncated model score was displayed.',413);return rows;}
