import {createHash} from 'node:crypto';
import {gzipSync,gunzipSync} from 'node:zlib';
import {ApiError} from '../auth';

const MARKER='_gridironGzipJson';
export const CLOUD_LEAF_LIMIT=20_000_000;
const THRESHOLD=128_000;
type Envelope={_gridironGzipJson:1;sha256:string;bytes:number;base64:string};

/** Lossless transport encoding of large private inputs/results. Outer job status,
 * identity, timestamps and result attestation stay directly queryable in JSONB. */
export function encodeCloudData(data:Record<string,any>){
 const result={...data};
 for(const key of ['input','result']){
  if(result[key]===undefined||result[key]===null)continue;
  const raw=Buffer.from(JSON.stringify(result[key]),'utf8');
  if(raw.length>CLOUD_LEAF_LIMIT)throw new ApiError('Complete research evidence exceeds the supported per-record size. No truncated evidence was saved.',413);
  if(raw.length<THRESHOLD)continue;
  result[key]={[MARKER]:1,sha256:createHash('sha256').update(raw).digest('hex'),bytes:raw.length,base64:gzipSync(raw,{level:6}).toString('base64')} satisfies Envelope;
 }
 return result;
}
export function decodeCloudData(data:Record<string,any>){
 const result={...data};
 for(const key of ['input','result']){
  const value=result[key];if(!value||typeof value!=='object'||value[MARKER]!==1)continue;
  if(Object.keys(value).sort().join(',')!=='_gridironGzipJson,base64,bytes,sha256'||!Number.isSafeInteger(value.bytes)||value.bytes<0||value.bytes>CLOUD_LEAF_LIMIT||typeof value.base64!=='string'||value.base64.length>Math.ceil(CLOUD_LEAF_LIMIT*4/3)+8||!(/^[a-f0-9]{64}$/.test(value.sha256)))throw new ApiError('Saved research encoding is invalid or exceeds the supported recovery size.',503);
  try{
   const raw=gunzipSync(Buffer.from(value.base64,'base64'),{maxOutputLength:Math.min(CLOUD_LEAF_LIMIT,value.bytes+1)});
   if(raw.length!==value.bytes||createHash('sha256').update(raw).digest('hex')!==value.sha256)throw Error('integrity');
   result[key]=JSON.parse(raw.toString('utf8'));
  }catch{throw new ApiError('Saved research evidence failed its encoding integrity check. Original records were preserved.',503);}
 }
 return result;
}
