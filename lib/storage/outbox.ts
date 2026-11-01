import {cloudClient} from '../cloud/context';
import type {ResearchDocument} from './schema';
import type {LegacyResearchPointer} from '../public-nfl/objects';
export type Delivery={id:string;document_info:Omit<ResearchDocument,'payload'>;stage:LegacyResearchPointer;lease:string;attempts:number};
export async function storageOperation(payload:Record<string,unknown>){const token=process.env.GRIDIRON_PUBLIC_INGEST_TOKEN;if(!token||token.length<40)throw Error('Storage coordination is not configured.');const {data,error}=await cloudClient().rpc('gridiron_storage_operation',{token,payload});if(error)throw Error('Storage coordination unavailable. Durable staged research remains intact.');return data;}
export async function enqueueResearch(document:ResearchDocument,stage:LegacyResearchPointer){const{payload,...metadata}=document;return storageOperation({action:'enqueue',id:document._id,document:metadata,stage});}
export async function deliverResearchQueue(limit=5){
 const {mongoConfigured,mongoResearch}=await import('./mongo');if(!mongoConfigured())return{status:'not_configured',delivered:0,failed:0};
 const {readResearchObject}=await import('../public-nfl/objects');const rows:Delivery[]=await storageOperation({action:'claim',limit});let delivered=0,failed=0;
 for(const row of rows){try{const payload=await readResearchObject(row.stage);const {verifyResearchDocument}=await import('./schema');const document={...row.document_info,payload};verifyResearchDocument(document,row.id,row.document_info.sha256);const receipt=await(await mongoResearch()).put(document);await storageOperation({action:'ack',id:row.id,lease:row.lease,sha256:receipt.sha256});delivered++;}catch{failed++;await storageOperation({action:'fail',id:row.id,lease:row.lease,code:'research_delivery_failed'}).catch(()=>{});}}
 return{status:failed?'partial':'completed',delivered,failed};
}
