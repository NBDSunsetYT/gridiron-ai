import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {ApiError} from '../lib/auth';
const state=vi.hoisted(()=>({rows:[] as any[],failKind:'',conflictKind:''}));
vi.mock('../lib/cloud/store',async importOriginal=>{
 const original=await importOriginal<typeof import('../lib/cloud/store')>();
 const select=(ctx:any,kind:string,options:any={})=>state.rows.filter(r=>r.user_id===ctx.user.id&&r.kind===kind&&(options.entityKey===undefined||r.entity_key===options.entityKey)).slice(0,options.limit??Infinity);
 return {...original,records:vi.fn(async(ctx:any,kind:string,options:any)=>select(ctx,kind,options)),allRecords:vi.fn(async(ctx:any,kind:string)=>select(ctx,kind)),record:vi.fn(async(ctx:any,id:string,kind?:string)=>{const row=state.rows.find(r=>r.user_id===ctx.user.id&&r.id===id&&(!kind||r.kind===kind));if(!row)throw new ApiError('Owned record not found.',404);return row;}),saveRecord:vi.fn(async(ctx:any,kind:string,data:any,options:any={})=>{
  if(state.failKind===kind){state.failKind='';throw new ApiError('SYNTHETIC temporary write failure',503);}
  const id=options.id??data.id;if(state.rows.some(r=>r.id===id))throw new ApiError('SYNTHETIC duplicate',409);
  const row={id,user_id:ctx.user.id,kind,data:structuredClone(data),entity_key:options.entityKey??'',created_at:data.createdAt,updated_at:data.createdAt};state.rows.unshift(row);
  if(state.conflictKind===kind){state.conflictKind='';throw new ApiError('SYNTHETIC concurrent insert conflict',409);}
  return data;
 })};
});
import {cloudSaveInjury} from '../lib/cloud/research';
const ctx=(id='SYNTHETIC-OWNER')=>({user:{id}} as any);
const report=()=>({entityKey:'SYNTHETIC-PLAYER',player:'SYNTHETIC PLAYER',team:'SYNTHETIC TEAM',status:'questionable',practiceParticipation:'limited',publicationAt:'2026-10-29T12:00:00.000Z',checkedAt:'2026-10-29T13:00:00.000Z',sourceUrl:'https://www.nfl.com/injuries/',sourceName:'SYNTHETIC TEST CITATION',sourceType:'official',verified:true,note:'SYNTHETIC TEST RECORD'});
const rows=(kind:string)=>state.rows.filter(r=>r.kind===kind);
function seed(owner='SYNTHETIC-OWNER'){
 state.rows.unshift({id:'SYNTHETIC-PREDICTION',user_id:owner,kind:'prediction_snapshots',entity_key:'contract',created_at:'2026-10-29T11:00:00.000Z',data:{id:'SYNTHETIC-PREDICTION',contractId:'SYNTHETIC-CONTRACT',eventStart:'2026-11-01T18:00:00.000Z',injuryEntityKeys:['SYNTHETIC-PLAYER'],injuryVersions:[],evidence:{simulationId:'SYNTHETIC-SOURCE-JOB'}}},{id:'SYNTHETIC-INPUTS-'+owner,user_id:owner,kind:'simulation_inputs',entity_key:'SYNTHETIC-SOURCE-JOB',created_at:'2026-10-29T10:00:00.000Z',data:{input:{}}});
}
beforeEach(()=>{state.rows=[];state.failKind='';state.conflictKind='';vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-30T00:00:00Z'));seed();});
afterEach(()=>vi.useRealTimers());
describe('Cloud injury evidence and durable queue reconciliation',()=>{
 it('repairs a failed notification insert after the immutable injury was saved',async()=>{
  state.failKind='notification_history';await expect(cloudSaveInjury(ctx(),report())).rejects.toThrow(/temporary/);expect(rows('injury_history')).toHaveLength(1);expect(rows('simulation_jobs')).toHaveLength(0);
  const existing=structuredClone(rows('injury_history')[0]);const retry=await cloudSaveInjury(ctx(),report());expect(retry.record.id).toBe(existing.id);expect(rows('injury_history')).toEqual([existing]);expect(rows('notification_history')).toHaveLength(1);expect(rows('simulation_jobs')).toHaveLength(1);expect(rows('simulation_jobs')[0].data.status).toBe('queued');
 });
 it('repairs a job insert failure without duplicating the already saved notification',async()=>{
  state.failKind='simulation_jobs';await expect(cloudSaveInjury(ctx(),report())).rejects.toThrow(/temporary/);expect(rows('notification_history')).toHaveLength(1);await cloudSaveInjury(ctx(),report());expect(rows('injury_history')).toHaveLength(1);expect(rows('notification_history')).toHaveLength(1);expect(rows('simulation_jobs')).toHaveLength(1);
 });
 it('retries without overwriting or duplicating completed jobs or historical evidence',async()=>{
  await cloudSaveInjury(ctx(),report());const job=rows('simulation_jobs')[0];job.data={...job.data,status:'completed',result:{label:'SYNTHETIC retained result'}};const before=structuredClone(state.rows);await cloudSaveInjury(ctx(),report());expect(state.rows).toEqual(before);
 });
 it('recognizes legacy random-id completed jobs for the same injury facts',async()=>{
  const first=await cloudSaveInjury(ctx(),report()),job=rows('simulation_jobs')[0];job.id='SYNTHETIC-LEGACY-RANDOM-ID';job.data.id=job.id;job.data.status='completed';delete job.data.data.factsHash;expect(job.data.data.injuryRecordId).toBe(first.record.id);await cloudSaveInjury(ctx(),report());expect(rows('simulation_jobs')).toHaveLength(1);expect(rows('simulation_jobs')[0].data.status).toBe('completed');
 });
 it('captures a verified practice change as new facts without inventing availability weights',async()=>{
  const a=await cloudSaveInjury(ctx(),report()),b=await cloudSaveInjury(ctx(),{...report(),practiceParticipation:'did_not_participate',checkedAt:'2026-10-29T14:00:00Z'});expect(a.record.factsHash).not.toBe(b.record.factsHash);expect(b.record.practiceParticipation).toBe('did_not_participate');expect(b.record.availability).toBeNull();expect(rows('injury_history')).toHaveLength(2);expect(rows('simulation_jobs')).toHaveLength(2);
 });
 it('handles concurrent duplicate insert conflicts by retaining the owned saved records',async()=>{
  state.conflictKind='simulation_jobs';await cloudSaveInjury(ctx(),report());expect(rows('simulation_jobs')).toHaveLength(1);await cloudSaveInjury(ctx(),report());expect(rows('simulation_jobs')).toHaveLength(1);
 });
 it('scopes deterministic evidence and jobs to the authenticated owner',async()=>{
  const a=await cloudSaveInjury(ctx(),report());seed('SYNTHETIC-OTHER-OWNER');const b=await cloudSaveInjury(ctx('SYNTHETIC-OTHER-OWNER'),report());expect(a.record.id).not.toBe(b.record.id);const jobs=rows('simulation_jobs');expect(jobs).toHaveLength(2);expect(jobs[0].id).not.toBe(jobs[1].id);
 });
});
