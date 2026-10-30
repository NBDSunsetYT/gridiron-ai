import {createHash} from 'node:crypto';
import {ApiError} from '../auth';
import {validateQuote,type ContractQuote} from '../contracts';
import {cloudError,requireCloudUser,type CloudContext} from './context';
import {records,unwrap} from './store';
import {canonicalJson} from './attestation';
export function importUuid(value:string){const hex=createHash('sha256').update(value).digest('hex').slice(0,32);return`${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;}
export function contractImportPlan(body:any){
 if(body?.verified!==true)throw new ApiError('Review and explicitly verify every exact contract field before importing.');
 if(!Array.isArray(body.quotes)||body.quotes.length<1||body.quotes.length>100)throw new ApiError('Import 1–100 reviewed contract quotes.');
 const normalized=body.quotes.map((input:any)=>{const{id,createdAt,source,...q}=validateQuote({...input,verified:true});return q;});
 const seen=new Map<string,any>();for(const quote of normalized){const previous=seen.get(quote.contractId);if(previous){for(const key of ['eventId','threshold','operator','eventStart','settlementRule'])if(previous[key]!==quote[key])throw new ApiError('The batch changes established rules under one contract identifier.');if(previous.settlementDefinition&&canonicalJson(previous.settlementDefinition)!==canonicalJson(quote.settlementDefinition))throw new ApiError('A batch cannot change a contract participant or structured rules.');}seen.set(quote.contractId,quote);}
 return{quotes:normalized,digest:createHash('sha256').update(canonicalJson(normalized)).digest('hex')};
}
export async function cloudImportContracts(ctx:CloudContext,body:unknown){
 const user=requireCloudUser(ctx),{quotes,digest}=contractImportPlan(body),previousReceipt=unwrap(await records(ctx,'contract_import_receipts',{entityKey:digest,limit:1}))[0];
 if(previousReceipt)return{...previousReceipt,imported:0,duplicate:true};
 const now=new Date().toISOString(),ids=quotes.map((_q:any,i:number)=>importUuid(`${user.id}:contract-quote:${digest}:${i}`));
 // Validate the existing history too. PostgreSQL's quote-identity trigger serializes concurrent inserts.
 for(const q of quotes){const existing=unwrap(await records(ctx,'contract_quotes',{entityKey:q.contractId}));for(const old of existing){for(const key of ['eventId','threshold','operator','eventStart','settlementRule'])if(old[key]!==q[key])throw new ApiError('A contract identifier cannot change its event or settlement rules.');if(old.settlementDefinition&&canonicalJson(old.settlementDefinition)!==canonicalJson(q.settlementDefinition))throw new ApiError('Established structured settlement definitions cannot change.');}}
 const receipt={id:importUuid(`${user.id}:contract-import:${digest}`),digest,imported:quotes.length,ids,duplicate:false,createdAt:now};
 const rows=quotes.map((q:any,i:number)=>({id:ids[i],user_id:user.id,kind:'contract_quotes',entity_key:q.contractId,data:{...q,id:ids[i],source:'manual_verified',createdAt:now},source:q.sourceUrl,observed_at:q.quotedAt,created_at:now,updated_at:now}));
 rows.push({id:receipt.id,user_id:user.id,kind:'contract_import_receipts',entity_key:digest,data:receipt,source:'verified user import',observed_at:now,created_at:now,updated_at:now});
 const inserted=await ctx.client.from('gridiron_records').insert(rows);
 if(inserted.error){if(inserted.error.code==='23505'){const retried=unwrap(await records(ctx,'contract_import_receipts',{entityKey:digest,limit:1}))[0];if(retried)return{...retried,imported:0,duplicate:true};}cloudError(inserted.error);}
 return receipt;
}
