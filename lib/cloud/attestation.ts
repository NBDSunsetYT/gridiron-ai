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
export function attestCloudResult(ctx:CloudContext,jobId:string,result:unknown){return{version:1,algorithm:'hmac-sha256',mac:mac(ctx,jobId,result)};}
export function verifyCloudResult(ctx:CloudContext,jobId:string,job:Record<string,any>){const proof=job.resultProof;if(proof?.version!==1||proof.algorithm!=='hmac-sha256'||typeof proof.mac!=='string'||!/^[a-f0-9]{64}$/.test(proof.mac))throw new ApiError('This saved result has no server attestation. Imported or externally edited outcomes must be rerun through the private service before being attached as generated forecasts.');const expected=Buffer.from(mac(ctx,jobId,job.result),'hex'),provided=Buffer.from(proof.mac,'hex');if(expected.length!==provided.length||!timingSafeEqual(expected,provided))throw new ApiError('Saved simulation provenance could not be authenticated. No generated probability was used.');}
export function verifiedCloudJob(ctx:CloudContext,job:Record<string,any>){
 if(job.status!=='completed')return job;
 try{verifyCloudResult(ctx,job.id,job);return{...job,provenanceVerified:true};}
 catch(error){return{...job,status:'provenance_unverified',originalStatus:job.status,result:null,provenanceVerified:false,error:error instanceof Error?error.message:'Generated result provenance could not be verified.',preservation:'The original record is retained in the database and encrypted export; rerun to display authenticated generated outputs.'};}
}
