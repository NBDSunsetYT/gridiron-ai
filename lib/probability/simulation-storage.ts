/** Durable compact public results. Existing private object store is the recovery
 * authority while Atlas/R2 are inactive. No account or financial data enters it. */
import {sharedCache,putCache} from '../public-nfl/store';
import {saveSharedResearch} from '../storage/research';
import {readResearchObject,isResearchPointer} from '../public-nfl/objects';
import {createHash} from 'node:crypto';
import {ApiError} from '../auth';
export function simulationStorageKey(sport:'NFL'|'CFB',gameId:string,count:number,inputHash:string){return'probability-run:'+createHash('sha256').update(JSON.stringify([sport,gameId,count,inputHash])).digest('hex');}
export async function readProbabilitySimulation(sport:'NFL'|'CFB',gameId:string,count:number,inputHash:string){
 const row=await sharedCache('analysis',simulationStorageKey(sport,gameId,count,inputHash));if(!row)return null;const data=row.data;
 if(data.sport!==sport||data.gameId!==gameId||data.simulations!==count||data.inputVersion!==inputHash||!isResearchPointer(data.reference))throw new ApiError('The saved simulation reference does not match these verified inputs.',502);
 const payload=await readResearchObject(data.reference);if(payload.sport!==sport||payload.gameId!==gameId||payload.inputVersion!==inputHash||payload.result?.simulations!==count)throw new ApiError('Saved simulation identity failed its integrity check.',502);
 return payload;
}
export async function saveProbabilitySimulation(sport:'NFL'|'CFB',gameId:string,count:number,inputHash:string,payload:Record<string,any>){
 if(payload.result?.simulations!==count||!Number.isFinite(Date.parse(payload.result?.eventStart)))throw new ApiError('A reconciled completed simulation is required.',502);
 const value={...payload,sport,gameId,inputVersion:inputHash},reference=await saveSharedResearch(sport,gameId,'simulation',value);
 // The metadata is small and uses the existing operational reserve, separately
 // from bulk quote admission. Previous immutable result objects are retained.
 await putCache('analysis',simulationStorageKey(sport,gameId,count,inputHash),{sport,gameId,simulations:count,inputVersion:inputHash,reference},inputHash,Math.max(60000,Date.parse(payload.result.eventStart)-Date.now()));
 if(payload.game)try{await(await import('../learning/store')).captureSimulation({...payload.game,sport},{id:payload.analysis?.id??payload.id??inputHash,createdAt:payload.analysis?.createdAt??payload.result.createdAt,inputVersion:inputHash,result:payload.result,research:payload.research},{resultReference:reference});}catch(error){await putCache('status','learning-capture:'+inputHash,{status:'pending',sport,gameId,message:error instanceof Error?error.message:'Learning snapshot archival pending.',reference},inputHash,86400000).catch(()=>{});}
 return value;
}
