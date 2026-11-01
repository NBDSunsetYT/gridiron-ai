import {S3Client,PutObjectCommand,GetObjectCommand,HeadBucketCommand,type S3ClientConfig} from '@aws-sdk/client-s3';
import {createHash} from 'node:crypto';
import {gzipSync,gunzipSync} from 'node:zlib';
export type R2Reference={version:1;backend:'r2';key:string;sha256:string;rawSha256:string;bytes:number;rawBytes:number;retention:'protected'|'temporary'};
export function r2Configured(){return Boolean(process.env.R2_ACCOUNT_ID&&process.env.R2_BUCKET&&process.env.R2_ACCESS_KEY_ID&&process.env.R2_SECRET_ACCESS_KEY);}
let client:S3Client|undefined;
export async function verifyPrivateR2Bucket(){
 const account=process.env.R2_ACCOUNT_ID,bucket=process.env.R2_BUCKET,token=process.env.CLOUDFLARE_R2_ADMIN_TOKEN;if(!account||!bucket||!token)throw Error('R2 public-access settings require account authorization before uploads.');
 const base=`https://api.cloudflare.com/client/v4/accounts/${account}/r2/buckets/${encodeURIComponent(bucket)}/domains/`;
 const values=await Promise.all(['managed','custom'].map(async path=>{const response=await fetch(base+path,{headers:{Authorization:`Bearer ${token}`},cache:'no-store',signal:AbortSignal.timeout(10000)});if(!response.ok)throw Error('R2 bucket privacy could not be verified.');const data=await response.json();if(data.success!==true||!data.result)throw Error('R2 privacy response is incomplete.');return data.result;}));
 if(values[0].enabled!==false||!Array.isArray(values[1].domains)||values[1].domains.some((d:any)=>d.enabled!==false))throw Error('R2 uploads are blocked because public bucket access is enabled or unverified.');
}
function configuredClient(){if(!r2Configured())throw Error('Private R2 storage is not configured.');if(!/^[a-f0-9]{32}$/i.test(process.env.R2_ACCOUNT_ID!)||!/^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/.test(process.env.R2_BUCKET!))throw Error('Invalid R2 account or bucket configuration.');
 const config:S3ClientConfig={region:'auto',endpoint:`https://${process.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,credentials:{accessKeyId:process.env.R2_ACCESS_KEY_ID!,secretAccessKey:process.env.R2_SECRET_ACCESS_KEY!},maxAttempts:2,requestChecksumCalculation:'WHEN_REQUIRED',responseChecksumValidation:'WHEN_REQUIRED'};
 return client??=new S3Client(config);
}
const hash=(v:Uint8Array)=>createHash('sha256').update(v).digest('hex');
/** No ACL, public bucket policy, signed browser URL or caller-chosen host. */
export class PrivateR2Store{
 constructor(private s3:Pick<S3Client,'send'>=configuredClient(),private bucket=process.env.R2_BUCKET!,private verifyPrivacy=verifyPrivateR2Bucket){}
 async put(raw:Uint8Array,kind:'datasets'|'artifacts'|'archives'|'temporary',sport:'NFL'|'CFB'):Promise<R2Reference>{if(!['NFL','CFB'].includes(sport)||!['datasets','artifacts','archives','temporary'].includes(kind)||raw.length>200_000_000)throw Error('Unsupported bounded archive.');const body=gzipSync(raw,{level:6}),sha256=hash(body),key=`${kind}/${sport}/${sha256}.gz`,ref:R2Reference={version:1,backend:'r2',key,sha256,rawSha256:hash(raw),bytes:body.length,rawBytes:raw.length,retention:kind==='temporary'?'temporary':'protected'};
  await this.verifyPrivacy();try{await this.s3.send(new PutObjectCommand({Bucket:this.bucket,Key:key,Body:body,ContentType:'application/gzip',IfNoneMatch:'*',Metadata:{sha256,rawsha256:ref.rawSha256,retention:ref.retention}}),{abortSignal:AbortSignal.timeout(60000)});}catch(error:any){if(error?.$metadata?.httpStatusCode!==412)throw Error('R2 upload unavailable; no archive was marked saved.');}
  const verified=await this.get(ref);if(hash(verified)!==ref.rawSha256)throw Error('R2 archive receipt failed integrity verification.');return ref;
 }
 async get(ref:R2Reference){if(ref.backend!=='r2'||! /^(datasets|artifacts|archives|temporary)\/(NFL|CFB)\/[a-f0-9]{64}\.gz$/.test(ref.key)||!ref.key.endsWith(ref.sha256+'.gz')||ref.rawBytes<0||ref.rawBytes>200_000_000||ref.bytes>200_000_000)throw Error('Invalid private archive reference.');const value=await this.s3.send(new GetObjectCommand({Bucket:this.bucket,Key:ref.key}),{abortSignal:AbortSignal.timeout(60000)});if(!value.Body)throw Error('R2 object is missing.');const chunks:Uint8Array[]=[];let size=0;for await(const chunk of value.Body as any){size+=chunk.length;if(size>ref.bytes||size>200_000_000)throw Error('R2 object exceeds its integrity bound.');chunks.push(chunk);}const compressed=Buffer.concat(chunks);if(size!==ref.bytes||hash(compressed)!==ref.sha256)throw Error('R2 compressed checksum mismatch.');const raw=gunzipSync(compressed,{maxOutputLength:200_000_000});if(raw.length!==ref.rawBytes||hash(raw)!==ref.rawSha256)throw Error('R2 archive checksum mismatch.');return raw;}
 async health(){await this.verifyPrivacy();await this.s3.send(new HeadBucketCommand({Bucket:this.bucket}),{abortSignal:AbortSignal.timeout(10000)});return{reachable:true,privacy:'Verified: managed r2.dev access disabled; no enabled custom domains.'};}
}
