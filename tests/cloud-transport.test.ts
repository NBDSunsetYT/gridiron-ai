import {afterEach,describe,expect,it,vi} from 'vitest';
import {cloudJson,compactSimulationJob,compactSimulationResult} from '../lib/cloud/transport';

afterEach(()=>vi.unstubAllEnvs());
const fit=(large=false)=>({
 summary:{plays:25303,games:180},
 provenance:'SYNTHETIC transport fixture; not NFL model evidence',
 model:{version:'SYNTHETIC-ARTIFACT',sha256:'synthetic-input-hash',asOf:'2023-11-30T00:00:00Z',source:'SYNTHETIC transport fixture',teams:['SYNTH-A','SYNTH-B'],modelOptions:{conditionalShrinkage:true},dataAvailabilityVerified:false,signature:'SYNTHETIC-PRIVATE-SIGNATURE',rows:large?[{payload:'x'.repeat(12*1024*1024)}]:[{yards:1}],privateArbitraryBulk:'must stay in the saved artifact'},
});

describe('Compact hosted simulation transport',()=>{
 it('preserves the complete fitted artifact when compact transport is disabled',()=>{
  vi.stubEnv('GRIDIRON_COMPACT_API','0');const original=fit();
  expect(compactSimulationResult('owned-fit-job',original)).toEqual(original);
  expect(compactSimulationResult('owned-fit-job',original)).not.toHaveProperty('modelReferenceOnly');
 });
 it('reduces a 12 MB fitted artifact to a small explicit reference without mutating stored evidence',()=>{
  vi.stubEnv('GRIDIRON_COMPACT_API','1');const original=fit(true),output=compactSimulationResult('owned-fit-job',original);
  expect(Buffer.byteLength(JSON.stringify(original))).toBeGreaterThan(12*1024*1024);
  expect(Buffer.byteLength(JSON.stringify(output))).toBeLessThan(5000);
  expect(output).toMatchObject({summary:original.summary,provenance:original.provenance,modelJobId:'owned-fit-job',modelReferenceOnly:true});
  expect(output.model).toEqual({version:'SYNTHETIC-ARTIFACT',sha256:'synthetic-input-hash',asOf:'2023-11-30T00:00:00Z',source:'SYNTHETIC transport fixture',teams:['SYNTH-A','SYNTH-B'],modelOptions:{conditionalShrinkage:true},dataAvailabilityVerified:false});
  expect(output.model).not.toHaveProperty('rows');expect(output.model).not.toHaveProperty('signature');expect(output.model).not.toHaveProperty('privateArbitraryBulk');
  expect(original.model.rows[0]).toHaveProperty('payload');expect(original.model.signature).toBe('SYNTHETIC-PRIVATE-SIGNATURE');
 });
 it('keeps simulation probabilities and distributions unchanged rather than replacing them with fit metadata',()=>{
  vi.stubEnv('GRIDIRON_COMPACT_API','1');const run={simulations:10000,homeWinProbability:.5,players:{'SYNTH-A-QB':{passingYards:{histogram:[{value:100,count:10000}]}}},contracts:[{id:'synthetic-total',probability:.5}],jointOutcomes:[{outcomes:['yes'],count:5000},{outcomes:['no'],count:5000}]};
  expect(compactSimulationResult('owned-simulation-job',run)).toEqual(run);
 });
 it('compacts only the verified job result while retaining its actual status and provenance fields',()=>{
  vi.stubEnv('GRIDIRON_COMPACT_API','true');const result=fit(),job={id:'owned-fit-job',kind:'fit',status:'completed',provenanceVerified:true,resultProof:{version:1,mac:'SYNTHETIC-PROOF'},data:{inputHash:'synthetic-hash'},result};
  const output=compactSimulationJob(job);
  expect(output).toMatchObject({id:job.id,kind:'fit',status:'completed',provenanceVerified:true,resultProof:job.resultProof,data:job.data});
  expect(output.result.modelJobId).toBe(job.id);expect(output.result.modelReferenceOnly).toBe(true);expect(output.result.model).not.toHaveProperty('rows');expect(job.result.model.rows).toHaveLength(1);
 });
 it('streams a large Unicode JSON body in bounded chunks with an exact round trip and private cache policy',async()=>{
  vi.stubEnv('GRIDIRON_COMPACT_API','1');const value={label:'SYNTHETIC JSON streaming fixture',text:'🏈é漢字'.repeat(160000),zero:0,flag:false};
  const response=cloudJson(value,201);expect(response.status).toBe(201);expect(response.headers.get('content-type')).toContain('application/json');expect(response.headers.get('cache-control')).toContain('no-store');expect(response.headers.has('content-length')).toBe(false);
  const chunks:Uint8Array[]=[];const reader=response.body!.getReader();for(;;){const next=await reader.read();if(next.done)break;chunks.push(next.value);}
  expect(chunks.length).toBeGreaterThan(1);expect(chunks.every(chunk=>chunk.byteLength<=64*1024)).toBe(true);
  expect(JSON.parse(Buffer.concat(chunks).toString('utf8'))).toEqual(value);
 });
 it('retains ordinary JSON response semantics for small payloads',async()=>{
  vi.stubEnv('GRIDIRON_COMPACT_API','1');const value={status:'queued',pending:true,id:'synthetic-job'};
  const response=cloudJson(value,202);expect(response.status).toBe(202);expect(await response.json()).toEqual(value);expect(response.headers.get('cache-control')).toContain('no-store');
 });
});
