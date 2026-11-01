import {cloudContext,finishCloud} from '@/lib/cloud/context';
import {ApiError,errorResponse,guardMutation,readJsonObject} from '@/lib/auth';
import {requireStorageAdmin} from '@/lib/storage/health';
import {PrivateR2Store,r2Configured} from '@/lib/storage/r2';
import {storageOperation} from '@/lib/storage/outbox';
import {researchDocument} from '@/lib/storage/schema';
import {sharedJob} from '@/lib/public-nfl/store';
import {collegeOwnedAnalysis} from '@/lib/college-football/store';
import {canonicalJson} from '@/lib/cloud/attestation';
export const runtime='nodejs';export const dynamic='force-dynamic';export const maxDuration=120;
/** Explicitly requested, selected aggregate archive. Does not collect/store all generated plays. */
export async function POST(request:Request){let ctx;try{guardMutation(request);ctx=await cloudContext(request);requireStorageAdmin(ctx);if(!r2Configured())throw new ApiError('Private R2 archival is not configured. Existing research is unchanged.',503);const body=await readJsonObject(request);if(Object.keys(body).some(k=>!['sport','gameId','analysisId','archiveRequested'].includes(k))||!['NFL','CFB'].includes(body.sport)||typeof body.gameId!=='string'||typeof body.analysisId!=='string'||body.archiveRequested!==true)throw new ApiError('Choose a saved run and explicitly request its archive.');
 let result:any,research:any;if(body.sport==='NFL'){const job=await sharedJob(body.analysisId);if(!job||job.status!=='completed'||job.game_id!==body.gameId)throw new ApiError('Completed shared NFL run not found.',404);result=job.result?.result;research=job.result?.research??null;}else{const owned=await collegeOwnedAnalysis(ctx,body.analysisId);if(owned.analysis.gameId!==body.gameId)throw new ApiError('Choose the owned college run for this game.',404);result=owned.analysis.result;research=owned.analysis.research??null;}
 const document=researchDocument(body.sport,body.gameId,'simulation',{sport:body.sport,gameId:body.gameId,result,research,archiveKind:'aggregate_and_representative_games'}),reference=await new PrivateR2Store().put(Buffer.from(canonicalJson(document.payload)),'archives',body.sport);await storageOperation({action:'archive_record',id:reference.sha256,sport:body.sport,kind:'archives',reference});return finishCloud(ctx,Response.json({saved:true,archiveKind:'aggregate_and_representative_games',reference,allGeneratedGamesArchived:false,allGeneratedPlaysArchived:false}));
 }catch(error){return finishCloud(ctx,errorResponse(error instanceof ApiError?error:new ApiError('Archive could not be verified. Existing research and staged data were preserved.',503)));}}
