import {createHmac,timingSafeEqual} from 'node:crypto';
import {ApiError} from '../auth';
import {requireCloudUser,type CloudContext} from './context';
/** JSONB may reorder object keys, so proofs use a deterministic JSON representation. */
export function canonicalJson(value:any):string{
 if(value===null||typeof value!=='object')return JSON.stringify(value);
 if(Array.isArray(value))return'['+value.map(canonicalJson).join(',')+']';
 return'{'+Object.keys(value).sort().filter(k=>value[k]!==undefined).map(k=>JSON.stringify(k)+':'+canonicalJson(value[k])).join(',')+'}';
}
function mac(ctx:CloudContext,jobId:string,result:unknown){const secret=process.env.SIMULATION_SERVICE_TOKEN;if(!secret||secret.length<32)throw new ApiError('The stable private simulation secret is required to verify generated result provenance.',503);return createHmac('sha256',secret).update('GRIDIRON-CLOUD-RESULT-V1\n').update(requireCloudUser(ctx).id+'\n'+jobId+'\n').update(canonicalJson(result)).digest('hex');}
/** Numeric leaves use IEEE754 bytes so the Python worker, JavaScript and
 * PostgreSQL agree on integer/float notation without trusting client results. */
export function numericCanonicalJson(value:any):string{
 function tree(v:any):any{
  if(v===null)return ['null'];
  if(typeof v==='boolean')return ['bool',v];
  if(typeof v==='number'){if(!Number.isFinite(v))throw new ApiError('A generated result contains a nonfinite number.');const bytes=Buffer.alloc(8);bytes.writeDoubleBE(v===0?0:v);return ['number',bytes.toString('hex')];}
  if(typeof v==='string')return ['string',v];
  if(Array.isArray(v))return ['array',v.map(tree)];
  if(v&&typeof v==='object')return ['object',Object.keys(v).sort().filter(k=>v[k]!==undefined).map(k=>[k,tree(v[k])])];
  throw new ApiError('A generated result contains unsupported data.');
 }
 return JSON.stringify(tree(value));
}
export function workerResultMac(ctx:CloudContext,jobId:string,result:unknown){const secret=process.env.SIMULATION_SERVICE_TOKEN;if(!secret||secret.length<32)throw new ApiError('The private simulation secret is unavailable.',503);return createHmac('sha256',secret).update('GRIDIRON-CLOUD-RESULT-V2\n'+requireCloudUser(ctx).id+'\n'+jobId+'\n').update(numericCanonicalJson(result)).digest('hex');}
export function cloudInputMac(ctx:CloudContext,jobId:string,input:unknown){const secret=process.env.SIMULATION_SERVICE_TOKEN;if(!secret||secret.length<32)throw new ApiError('The private simulation secret is unavailable.',503);return createHmac('sha256',secret).update('GRIDIRON-CLOUD-INPUT-V1\n'+requireCloudUser(ctx).id+'\n'+jobId+'\n').update(numericCanonicalJson(input)).digest('hex');}
export function attestCloudInput(ctx:CloudContext,jobId:string,input:unknown){return{version:1,algorithm:'hmac-sha256',mac:cloudInputMac(ctx,jobId,input)};}
export function attestCloudResult(ctx:CloudContext,jobId:string,result:unknown){return{version:1,algorithm:'hmac-sha256',mac:mac(ctx,jobId,result)};}
export function verifyCloudResult(ctx:CloudContext,jobId:string,job:Record<string,any>){const proof=job.resultProof;if(![1,2].includes(proof?.version)||proof.algorithm!=='hmac-sha256'||typeof proof.mac!=='string'||!/^[a-f0-9]{64}$/.test(proof.mac))throw new ApiError('This saved result has no server attestation. Imported or externally edited outcomes must be rerun through the private service before being attached as generated forecasts.');const expected=Buffer.from(proof.version===2?workerResultMac(ctx,jobId,job.result):mac(ctx,jobId,job.result),'hex'),provided=Buffer.from(proof.mac,'hex');if(expected.length!==provided.length||!timingSafeEqual(expected,provided))throw new ApiError('Saved simulation provenance could not be authenticated. No generated probability was used.');}
export function verifiedCloudJob(ctx:CloudContext,job:Record<string,any>){
 if(job.status!=='completed')return job;
 try{verifyCloudResult(ctx,job.id,job);return{...job,provenanceVerified:true};}
 catch(error){return{...job,status:'provenance_unverified',originalStatus:job.status,result:null,provenanceVerified:false,error:error instanceof Error?error.message:'Generated result provenance could not be verified.',preservation:'The original record is retained in the database and encrypted export; rerun to display authenticated generated outputs.'};}
}
