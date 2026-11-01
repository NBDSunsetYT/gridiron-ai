import {ApiError} from '../auth';
import {cloudClient,requireCloudUser,type CloudContext} from '../cloud/context';
import {saveRecord,record,records,unwrap} from '../cloud/store';
import {attestCloudResult,verifyCloudResult} from '../cloud/attestation';
import {encodeCloudData} from '../cloud/codec';
import {warehouseId} from '../warehouse';
import type {CollegeAnalysis,CollegeStorage,CollegeGame,ProviderQuote} from './types';

export const CFB_JOB_KIND='cfb_simulation_jobs';
export const CFB_SAVED_KIND='research_records/cfb_saved_simulation';
let storageCache:{expires:number;value:CollegeStorage}|null=null;
export async function footballStorage():Promise<CollegeStorage>{
 if(storageCache&&storageCache.expires>Date.now())return storageCache.value;
 let value:CollegeStorage={persistent:false,admissionAvailable:null,message:'Shared research persistence could not be verified. Private account records remain separate.'};
 try{const token=process.env.GRIDIRON_PUBLIC_INGEST_TOKEN;if(!token)throw Error();const response=await cloudClient().rpc('gridiron_football_data_write',{token,payload:{action:'status'}});if(response.error)throw Error();const available=response.data?.admissionAvailable===true;value={persistent:available,admissionAvailable:available,message:available?'Shared research storage is available. Individual saves require a verified database acknowledgment.':'The bulk market archive has reached its storage reserve. Game analysis and private account saves are checked separately; existing research remains preserved.'};}catch{/* Missing schema or service is not treated as a successful save. */}
 storageCache={expires:Date.now()+15000,value};return value;
}
export async function footballWrite(payload:Record<string,unknown>){
 const token=process.env.GRIDIRON_PUBLIC_INGEST_TOKEN;if(!token||token.length<40)throw new ApiError('Shared football research persistence is not configured.',503);
 const response=await cloudClient().rpc('gridiron_football_data_write',{token,payload});if(response.error){if(response.error.code==='54000'){if(/daily.*capacity/i.test(response.error.message))throw new ApiError('Daily complete-game research capacity is reached. Saved results remain available.',429);throw new ApiError('New shared research is paused to protect personal records. No history was deleted.',503);}throw new ApiError('Shared football research could not be saved. Existing records are preserved.',503);}return response.data;
}
export async function persistProviderQuotes(quotes:ProviderQuote[]){
 if(!Array.isArray(quotes)||quotes.length>100)throw new ApiError('Save at most100 verified provider quotes per bounded batch.');
 if(!quotes.length)return{saved:true,status:'empty',count:0};
 const state=await footballStorage();if(state.admissionAvailable!==true)return{saved:false,status:state.admissionAvailable===false?'paused_capacity':'unavailable',count:0,message:state.message};
 try{const result=await footballWrite({action:'batch',operations:quotes.map(quote=>({action:'provider_quote_put',quote}))});return{saved:true,status:'saved',count:Array.isArray(result)?result.length:quotes.length};}catch(error){return{saved:false,status:'unavailable',count:0,message:error instanceof Error?error.message:'Provider quotes were not saved.'};}
}
function verifyCollegeEvidence(ctx:CloudContext,id:string,data:Record<string,any>){
 verifyCloudResult(ctx,id,data);
 verifyCloudResult(ctx,id,{result:{sport:'CFB',game:data.game,research:data.research??null,publicAnalysisId:data.publicAnalysisId,modelVersion:data.modelVersion,inputVersion:data.inputVersion,createdAt:data.evidenceCreatedAt},resultProof:data.evidenceProof});
}
export async function saveCollegeAnalysis(ctx:CloudContext,analysis:CollegeAnalysis,game:CollegeGame){
 const user=requireCloudUser(ctx);if(analysis.sport!=='CFB'||game.sport!=='CFB'||analysis.gameId!==game.id||!analysis.result||analysis.result.sport!=='CFB')throw new ApiError('A verified college-football simulation is required.');
 const id=warehouseId(user.id,'cfb_simulation',analysis.id),existing=await record(ctx,id,CFB_JOB_KIND).catch(error=>{if(error instanceof ApiError&&error.status===404)return null;throw error;});
 if(existing){verifyCollegeEvidence(ctx,id,existing.data);return{id,saved:true,duplicate:true,sport:'CFB' as const};}
 const value={...analysis,id,evidenceCreatedAt:analysis.createdAt,publicAnalysisId:analysis.id,game,sport:'CFB',persistent:true,historySaved:true,resultProof:attestCloudResult(ctx,id,analysis.result),evidenceProof:attestCloudResult(ctx,id,{sport:'CFB',game,research:analysis.research??null,publicAnalysisId:analysis.id,modelVersion:analysis.modelVersion,inputVersion:analysis.inputVersion,createdAt:analysis.createdAt})};
 await saveRecord(ctx,CFB_JOB_KIND,encodeCloudData(value),{id,entityKey:game.id,source:'Verified college-football complete-game engine'});
 const bookmark=warehouseId(user.id,'cfb_saved_simulation',analysis.id);
 await saveRecord(ctx,CFB_SAVED_KIND,{id:bookmark,sport:'CFB',analysisId:id,gameId:game.id,modelVersion:analysis.modelVersion,simulations:analysis.simulations,savedAt:new Date().toISOString(),title:game.away.name+' at '+game.home.name},{id:bookmark,entityKey:game.id,source:'User-approved college-football save'});
 return{id,saved:true,duplicate:false,sport:'CFB' as const};
}
export async function collegeSavedResearch(ctx:CloudContext){
 requireCloudUser(ctx);const [jobRows,saved,predictions,reports]=await Promise.all([records(ctx,CFB_JOB_KIND,{limit:20}),records(ctx,CFB_SAVED_KIND,{limit:40}),records(ctx,'research_records/cfb_prediction_snapshot',{limit:40}),records(ctx,'research_records/cfb_saved_report',{limit:20})]);
 const jobs=jobRows.map(row=>{if(row.data.sport!=='CFB')throw new ApiError('A saved record has a different sport namespace.',409);verifyCollegeEvidence(ctx,row.id,row.data);const value=row.data;return{id:row.id,sport:'CFB',gameId:value.gameId,game:value.game,modelVersion:value.modelVersion,simulations:value.simulations,status:value.status,stale:Date.parse(value.game?.startTime??'')<=Date.now(),createdAt:value.evidenceCreatedAt,result:value.result?{homeWinProbability:value.result.homeWinProbability,awayWinProbability:value.result.awayWinProbability,tieProbability:value.result.tieProbability,scoreDistributions:value.result.scoreDistributions,modelVersion:value.result.modelVersion}:null};});
 return{sport:'CFB' as const,jobs,saved:unwrap(saved),predictions:unwrap(predictions),reports:unwrap(reports)};
}
export async function collegeOwnedAnalysis(ctx:CloudContext,id:string){const value=await record(ctx,id,CFB_JOB_KIND);if(value.data.sport!=='CFB')throw new ApiError('Choose an owned college-football result.',404);verifyCollegeEvidence(ctx,id,value.data);return{sport:'CFB' as const,analysis:{...value.data,id,createdAt:value.data.evidenceCreatedAt,stale:Date.parse(value.data.game?.startTime??'')<=Date.now()}};}

/** Only authenticated, fully attested source context may supply independent owner projections. */
export async function collegeSavedAnalyses(ctx:CloudContext){
 requireCloudUser(ctx);const rows=await records(ctx,CFB_JOB_KIND,{limit:5});return rows.map(row=>{verifyCollegeEvidence(ctx,row.id,row.data);if(row.data.sport!=='CFB'||row.data.game?.sport!=='CFB')throw new ApiError('A saved result has a different sport namespace.',409);return{game:row.data.game as CollegeGame,analysis:{...row.data,id:row.id,createdAt:row.data.evidenceCreatedAt,stale:Date.parse(row.data.game.startTime)<=Date.now()} as CollegeAnalysis};});
}
