import {describe,it,expect,vi,afterEach} from 'vitest';
import {gzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {encodeCloudData,decodeCloudData,CLOUD_LEAF_LIMIT} from '../lib/cloud/codec';
import {cloudFetch} from '../lib/cloud/context';
afterEach(()=>vi.unstubAllGlobals());
describe('Lossless bounded cloud research transport',()=>{
 it('round-trips large signed results without changing queryable job status or claims',()=>{
  const original={id:'synthetic-job',kind:'injury_resimulation',status:'completed',updatedAt:'2026-10-30T00:00:00Z',data:{sourceJobId:'original'},result:{rows:Array.from({length:5000},(_,i)=>({player:'Synthetic unicode 🏈',yards:i/10})),signature:'server-attested'},resultProof:{signature:'unchanged'}};
  const encoded=encodeCloudData(original);
  expect(encoded.status).toBe('completed');expect(encoded.kind).toBe('injury_resimulation');expect(encoded.data).toEqual(original.data);expect(encoded.resultProof).toEqual(original.resultProof);
  expect(encoded.result._gridironGzipJson).toBe(1);expect(JSON.stringify(encoded).length).toBeLessThan(JSON.stringify(original).length/2);expect(decodeCloudData(encoded)).toEqual(original);
 });
 it('keeps injury queued/running claim fields and small ordinary contracts unchanged',()=>{
  const job={kind:'injury_resimulation',status:'queued',data:{injuryRecordId:'synthetic'},result:null};expect(encodeCloudData(job)).toEqual(job);
  const quote={contractId:'synthetic',threshold:45.5,settlementRules:'strictly greater',result:'unsettled'};expect(encodeCloudData(quote)).toEqual(quote);
 });
 it('round-trips full replay inputs and rejects damaged evidence',()=>{
  const input={input:{csv:'historical,source,data\n'.repeat(10000)},jobId:'synthetic'};const packed=encodeCloudData(input);expect(decodeCloudData(packed)).toEqual(input);
  expect(()=>decodeCloudData({...packed,input:{...packed.input,sha256:'0'.repeat(64)}})).toThrow(/integrity/);
  expect(()=>decodeCloudData({...packed,input:{...packed.input,bytes:17}})).toThrow(/integrity/);
 });
 it('bounds declared and actual decompressed bytes and never returns a partial record',()=>{
  const bomb=Buffer.from('x'.repeat(100000));const packed={_gridironGzipJson:1,sha256:createHash('sha256').update(bomb).digest('hex'),bytes:5,base64:gzipSync(bomb).toString('base64')};
  expect(()=>decodeCloudData({result:packed})).toThrow(/integrity/);expect(()=>decodeCloudData({result:{...packed,bytes:CLOUD_LEAF_LIMIT+1}})).toThrow(/recovery size/);
 });
 it('adds a provider deadline while honoring an existing cancellation signal',async()=>{
  const fetch=vi.fn(async(_input,init)=>new Response(String(init.signal.aborted),{status:200}));vi.stubGlobal('fetch',fetch);const cancellation=AbortSignal.abort();const response=await cloudFetch('https://example.test',{signal:cancellation});expect(await response.text()).toBe('true');expect(fetch).toHaveBeenCalledOnce();
 });
});
