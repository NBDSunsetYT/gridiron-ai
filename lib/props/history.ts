import {cloudClient} from '../cloud/context';
import {thresholdKey} from './view';
import {ApiError} from '../auth';
import {readResearchObject,isResearchPointer} from '../public-nfl/objects';
export type HistorySelection={sport:'NFL'|'CFB';jobId:string;eventId:string;playerId:string;market:string;threshold:string;side:string;book:string;before?:number};
export async function automaticPropHistory(selection:HistorySelection){
 const token=process.env.GRIDIRON_PUBLIC_INGEST_TOKEN;if(!token)throw new ApiError('Research history is temporarily unavailable.',503);
 const {data,error}=await cloudClient().rpc('gridiron_auto_prop_history',{token,job_id:selection.jobId,before_id:selection.before??null});if(error||!Array.isArray(data))throw new ApiError('Stored research history could not be retrieved. Previous snapshots remain intact.',503);
 const pages=await Promise.all(data.map(async(meta:any)=>{if(!isResearchPointer(meta.result_ref))return[];const value=await readResearchObject(meta.result_ref);if(value.sport!==selection.sport||!Array.isArray(value.estimates))return[];
  const matches=value.estimates.filter((r:any)=>r.sport===selection.sport&&r.eventId===selection.eventId&&r.playerId===selection.playerId&&r.market===selection.market&&thresholdKey(r.threshold)===thresholdKey(selection.threshold)&&r.side===selection.side&&r.sourceQuote?.book===selection.book);if(matches.length!==1)return[];return matches.map((r:any)=>({id:String(meta.id),storedAt:meta.created_at,probability:r.calibratedProbability??r.estimateProbability??r.posteriorProbability??r.rawProbability??r.empiricalProbability??null,method:r.method,rawProbability:r.rawProbability??null,posteriorProbability:r.posteriorProbability??null,empiricalProbability:r.empiricalProbability??null,calibratedProbability:r.calibratedProbability??null,modelVersion:r.modelVersion,inputVersion:r.inputVersion,calculatedAt:r.calculatedAt,interval95:r.interval95??null,sourceQuote:r.sourceQuote,assumptions:r.assumptions,gameId:r.gameId}));
 }));
 const points=pages.flat().filter((p:any)=>typeof p.probability==='number'&&Number.isFinite(p.probability)&&p.probability>=0&&p.probability<=1).reverse().map((p:any,i:number,all:any[])=>({...p,changeReason:!i?'First snapshot on this page':p.modelVersion!==all[i-1].modelVersion?'Model version changed':p.inputVersion!==all[i-1].inputVersion?'Verified model inputs changed':p.probability!==all[i-1].probability?'Estimate changed; inspect assumptions':'Market observation refreshed; independent estimate reused'}));
 return{sport:selection.sport,points,nextBefore:data.length===8?Number(data.at(-1).id):null,immutable:true,scope:'Exact saved public selection. Historical snapshots are not current offers.'};
}
