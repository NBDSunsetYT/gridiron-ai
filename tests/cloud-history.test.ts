import {describe,it,expect} from 'vitest';
import {cloudConversation} from '../lib/cloud/research';
import {records,allRecords} from '../lib/cloud/store';
import {encodeCloudData} from '../lib/cloud/codec';

const OWNER='10000000-0000-4000-8000-000000000001';
const CONVERSATION='20000000-0000-4000-8000-000000000001';
function context(tables:Record<string,any[]>,serverPage=1000,counts?:Array<number|null>){
 const calls:{table:string;from:number;to:number;filters:Record<string,string>;countMode?:string}[]=[];
 const client={from(table:string){
  const filters:Record<string,string>={};let from=0,to=999,countMode:string|undefined;
  const matches=(row:any)=>Object.entries(filters).every(([key,value])=>key.startsWith('data->>')?row.data[key.slice(7)]===value:key.endsWith('<')?row[key.slice(0,-1)]<value:row[key]===value);
  const result=()=>{const source=(tables[table]??[]).filter(matches),index=calls.length;calls.push({table,from,to,filters:{...filters},countMode});return{data:source.slice(from,Math.min(to+1,from+serverPage)),count:counts?counts[index]??null:source.length,error:null};};
  const q={select(_columns:string,options?:{count:string}){countMode=options?.count;return q;},eq(key:string,value:string){filters[key]=value;return q;},lt(key:string,value:string){filters[key+'<']=value;return q;},order(){return q;},range(start:number,end:number){from=start;to=end;return q;},async maybeSingle(){const rows=(tables[table]??[]).filter(matches);return{data:rows[0]??null,error:null};},then(resolve:any,reject:any){return Promise.resolve(result()).then(resolve,reject);}};
  return q;
 }};
 return{ctx:{user:{id:OWNER},client} as any,calls};
}
const message=(i:number)=>({id:String(i).padStart(6,'0'),user_id:OWNER,conversation_id:CONVERSATION,role:i%2?'assistant':'user',content:'Saved message '+i,data:{ordinal:i},created_at:new Date(1700000000000+i*1000).toISOString()});
const saved=(i:number,data:any={ordinal:i})=>({id:String(i),user_id:OWNER,kind:'prediction_snapshots',entity_key:'contract',data,created_at:new Date(1700000000000+i*1000).toISOString()});
const conversation={id:CONVERSATION,user_id:OWNER,title:'Persisted history',created_at:'2024-01-01T00:00:00Z',updated_at:'2024-01-02T00:00:00Z'};

describe('Complete cloud history pagination',()=>{
 it('returns all chronological messages and the real newest AI context beyond 1000 rows under a smaller provider cap',async()=>{
  const rows=Array.from({length:1207},(_,i)=>message(i)),{ctx,calls}=context({conversations:[conversation],conversation_messages:rows},317);
  const result=await cloudConversation(ctx,CONVERSATION);
  expect(result.messages).toHaveLength(1207);expect(result.messages.at(-1)?.content).toBe('Saved message 1206');
  expect(result.messages.slice(-24).map(m=>m.data.ordinal)).toEqual(Array.from({length:24},(_,i)=>1183+i));
  expect(calls.map(c=>c.from)).toEqual([0,317,634,951]);
  expect(calls.every(c=>c.countMode==='exact'&&c.filters.user_id===OWNER&&c.filters.conversation_id===CONVERSATION)).toBe(true);
 });
 it('handles empty conversations and excludes another owner rather than leaking their messages',async()=>{
  const{ctx}=context({conversations:[conversation],conversation_messages:[{...message(0),user_id:'OTHER-OWNER'}]},7);
  expect((await cloudConversation(ctx,CONVERSATION)).messages).toEqual([]);
 });
 it('refuses an unstable or unverifiable conversation instead of returning incomplete history',async()=>{
  const tables={conversations:[conversation],conversation_messages:Array.from({length:4},(_,i)=>message(i))};
  await expect(cloudConversation(context(tables,2,[4,5]).ctx,CONVERSATION)).rejects.toMatchObject({status:409});
  await expect(cloudConversation(context(tables,2,[null]).ctx,CONVERSATION)).rejects.toMatchObject({status:503});
 });
 it('reads the complete model record with actual page offsets despite a provider cap below 1000',async()=>{
  const rows=Array.from({length:1201},(_,i)=>saved(i)),{ctx,calls}=context({gridiron_records:rows},500);
  expect((await allRecords(ctx,'prediction_snapshots')).map(r=>r.data.ordinal)).toEqual(rows.map(r=>r.data.ordinal));
  expect(calls.map(c=>c.from)).toEqual([0,500,1000]);expect(calls.every(c=>c.filters.user_id===OWNER&&c.countMode==='exact')).toBe(true);
 });
 it('honors explicit bounded-history limits while continuing through smaller source pages',async()=>{
  const{ctx,calls}=context({gridiron_records:Array.from({length:1201},(_,i)=>saved(i))},200);
  const result=await records(ctx,'prediction_snapshots',{limit:550,entityKey:'contract'});
  expect(result).toHaveLength(550);expect(result.at(-1)?.data.ordinal).toBe(549);expect(calls.map(c=>c.from)).toEqual([0,200,400]);
  expect(calls.every(c=>c.filters.entity_key==='contract'&&c.to<=549)).toBe(true);
 });
 it('rejects changing research counts and provider count failures before scoring a partial model history',async()=>{
  const tables={gridiron_records:Array.from({length:4},(_,i)=>saved(i))};
  await expect(allRecords(context(tables,2,[4,3]).ctx,'prediction_snapshots')).rejects.toMatchObject({status:409});
  await expect(records(context(tables,2,[null]).ctx,'prediction_snapshots')).rejects.toMatchObject({status:503});
 });
 it('filters injury queue kind, status and interruption age in PostgreSQL before applying history limits',async()=>{
  const rows=[...Array.from({length:120},(_,i)=>({...saved(i,{kind:'fit',status:'completed'}),kind:'simulation_jobs'})),{...saved(121,{kind:'injury_resimulation',status:'queued'}),kind:'simulation_jobs',updated_at:'2026-10-29T00:00:00Z'},{...saved(122,{kind:'injury_resimulation',status:'running'}),kind:'simulation_jobs',updated_at:'2026-10-29T00:00:00Z'},{...saved(123,{kind:'injury_resimulation',status:'running'}),kind:'simulation_jobs',updated_at:'2026-10-30T12:00:00Z'}];
  const{ctx,calls}=context({gridiron_records:rows});expect((await records(ctx,'simulation_jobs',{limit:1,dataKind:'injury_resimulation',dataStatus:'queued'}))[0].id).toBe('121');expect((await records(ctx,'simulation_jobs',{limit:1,dataKind:'injury_resimulation',dataStatus:'running',beforeUpdatedAt:'2026-10-30T00:00:00Z',oldestFirst:true}))[0].id).toBe('122');expect(calls.every(c=>c.filters['data->>kind']==='injury_resimulation')).toBe(true);
 });
 it('accounts for expanded compressed evidence when bounding complete-history memory',async()=>{
  const packed=encodeCloudData({result:{evidence:'x'.repeat(14_000_000)}});
  expect(JSON.stringify(packed).length).toBeLessThan(100000);
  const{ctx}=context({gridiron_records:[saved(0,packed),saved(1,packed),saved(2,packed)]},1);
  await expect(allRecords(ctx,'prediction_snapshots')).rejects.toMatchObject({status:413});
 });
});
