import {putResearchObject,readResearchObject,type LegacyResearchPointer} from '../public-nfl/objects';
import {researchDocument,ResearchIntegrityError,type Sport,type ResearchKind} from './schema';
import {enqueueResearch} from './outbox';
export type ExternalResearchPointer={_sharedResearchObject:{version:2;id:string;rawSha256:string;rawBytes:number;backend:'mongodb';stage:LegacyResearchPointer;documentId:string}};
/** A durable staging receipt precedes the outbox and external database write.
 * Supabase metadata + Atlas writes are deliberately not described as atomic. */
export async function saveSharedResearch(sport:Sport,gameId:string,kind:ResearchKind,value:Record<string,any>):Promise<LegacyResearchPointer|ExternalResearchPointer>{
 const document=researchDocument(sport,gameId,kind,value),stage=await putResearchObject(document.payload,true);
 const {mongoConfigured}=await import('./mongo');if(!mongoConfigured())return stage;
 try{await enqueueResearch(document,stage);}catch{return stage;}
 return{_sharedResearchObject:{version:2,backend:'mongodb',documentId:document._id,id:stage._sharedResearchObject.id,rawSha256:stage._sharedResearchObject.rawSha256,rawBytes:stage._sharedResearchObject.rawBytes,stage}};
}
export async function readExternalResearch(pointer:ExternalResearchPointer):Promise<Record<string,any>>{
 const {mongoConfigured,mongoResearch}=await import('./mongo'),p=pointer._sharedResearchObject;
 if(mongoConfigured())try{const value=await(await mongoResearch()).get(p.documentId,p.rawSha256);if(value)return value;}catch(error){if(error instanceof ResearchIntegrityError){const {storageOperation}=await import('./outbox');await storageOperation({action:'integrity_warning',id:p.documentId,code:'external_document_mismatch'}).catch(()=>{});}/* The verified durable stage remains the recovery copy. Never substitute guessed research. */}
 return readResearchObject(p.stage);
}
