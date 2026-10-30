import {randomUUID} from 'node:crypto';
import {getDb} from './db';
import {ApiError} from './auth';
function text(value:unknown,name:string,max=200):string{if(typeof value!=='string'||!value.trim()||value.length>max)throw new ApiError(`${name} is required and must be at most ${max} characters.`);return value.trim();}
function encodeJson(value:unknown,max=200_000):string {
  let serialized:string|undefined;
  try{serialized=JSON.stringify(value,(_key,v)=>{if(typeof v==='number'&&!Number.isFinite(v))throw new Error('Non-finite number');if(['bigint','function','symbol'].includes(typeof v))throw new Error('Non-JSON value');return v;});}catch{throw new ApiError('Data must contain valid finite JSON values.');}
  if(serialized===undefined||serialized.length>max)throw new ApiError(`JSON data must be present and at most ${max} characters.`);
  return serialized;
}
function date(value:unknown):string{if(value===undefined)return new Date().toISOString();const parsed=new Date(String(value));if(!Number.isFinite(parsed.getTime()))throw new ApiError('Invalid observation timestamp.');return parsed.toISOString();}
function conversationRow(row:Record<string,any>){return{id:row.id,title:row.title,createdAt:row.created_at,updatedAt:row.updated_at,messageCount:row.message_count??undefined};}
export function createConversation(userId:string,title='New research conversation'){
  const id=randomUUID(),now=new Date().toISOString();const safeTitle=text(title,'Title',200);
  getDb().prepare('INSERT INTO conversations(id,user_id,title,created_at,updated_at) VALUES(?,?,?,?,?)').run(id,userId,safeTitle,now,now);
  return{id,title:safeTitle,createdAt:now,updatedAt:now,messageCount:0};
}
export function listConversations(userId:string){
  return(getDb().prepare('SELECT c.*,(SELECT COUNT(*) FROM conversation_messages m WHERE m.conversation_id=c.id AND m.user_id=c.user_id) AS message_count FROM conversations c WHERE c.user_id=? ORDER BY c.updated_at DESC LIMIT 100').all(userId) as Record<string,any>[]).map(conversationRow);
}
export function getConversation(userId:string,id:string){
  const db=getDb();const row=db.prepare('SELECT * FROM conversations WHERE id=? AND user_id=?').get(id,userId) as Record<string,any>|undefined;
  if(!row)throw new ApiError('Conversation not found.',404);
  const messages=(db.prepare('SELECT * FROM conversation_messages WHERE conversation_id=? AND user_id=? ORDER BY created_at,rowid').all(id,userId) as Record<string,any>[]).map(m=>({id:m.id,role:m.role as 'user'|'assistant',content:m.content,data:JSON.parse(m.data),createdAt:m.created_at}));
  return{...conversationRow(row),messages};
}
export function appendMessage(userId:string,conversationId:string,input:{role:string;content:string;data?:unknown}){
  return getDb().transaction(()=>{
    getConversation(userId,conversationId);
    if(!['user','assistant'].includes(input.role))throw new ApiError('Message role must be user or assistant.');
    const content=text(input.content,'Message',40_000);const data=encodeJson(input.data??{},100_000);const id=randomUUID(),now=new Date().toISOString();
    getDb().prepare('INSERT INTO conversation_messages(id,conversation_id,user_id,role,content,data,created_at) VALUES(?,?,?,?,?,?,?)').run(id,conversationId,userId,input.role,content,data,now);
    getDb().prepare('UPDATE conversations SET updated_at=? WHERE id=? AND user_id=?').run(now,conversationId,userId);
    return{id,role:input.role as 'user'|'assistant',content,data:JSON.parse(data),createdAt:now};
  })();
}
export function deleteConversation(userId:string,id:string){const result=getDb().prepare('DELETE FROM conversations WHERE id=? AND user_id=?').run(id,userId);if(!result.changes)throw new ApiError('Conversation not found.',404);}
export function renameConversation(userId:string,id:string,title:string){getConversation(userId,id);getDb().prepare('UPDATE conversations SET title=?,updated_at=? WHERE id=? AND user_id=?').run(text(title,'Title'),new Date().toISOString(),id,userId);return getConversation(userId,id);}
export function getPreferences(userId:string){return Object.fromEntries((getDb().prepare('SELECT key,value FROM preferences WHERE user_id=? ORDER BY key').all(userId) as {key:string;value:string}[]).map(row=>[row.key,JSON.parse(row.value)]));}
export function setPreference(userId:string,key:string,value:unknown){
  const safeKey=text(key,'Preference key',80);if(!/^[a-zA-Z0-9_.-]+$/.test(safeKey))throw new ApiError('Invalid preference key.');
  const json=encodeJson(value,100_000);getDb().prepare('INSERT INTO preferences(user_id,key,value,updated_at) VALUES(?,?,?,?) ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at').run(userId,safeKey,json,new Date().toISOString());
  return value;
}
function recordRow(row:Record<string,any>){return{id:row.id,kind:row.kind,entityKey:row.entity_key,data:JSON.parse(row.data),source:row.source,observedAt:row.observed_at,createdAt:row.created_at,updatedAt:row.updated_at,recordOrigin:'user' as const};}
export function createResearchRecord(userId:string,input:{kind:string;entityKey?:string;data:unknown;source?:string;observedAt?:string}){
  const kind=text(input.kind,'Record kind',50);if(!/^[a-z][a-z0-9_-]*$/.test(kind))throw new ApiError('Invalid record kind.');
  const entityKey=input.entityKey?text(input.entityKey,'Entity key',200):'';const source=input.source?text(input.source,'Source',2000):'user';const data=encodeJson(input.data);const id=randomUUID(),now=new Date().toISOString(),observedAt=date(input.observedAt);
  getDb().prepare('INSERT INTO research_records(id,user_id,kind,entity_key,data,source,observed_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)').run(id,userId,kind,entityKey,data,source,observedAt,now,now);
  return{id,kind,entityKey,data:JSON.parse(data),source,observedAt,createdAt:now,updatedAt:now,recordOrigin:'user' as const};
}
export function listResearchRecords(userId:string,options:{kind?:string;entityKey?:string;limit?:number}={}){
  const limit=Math.min(500,Math.max(1,Math.floor(options.limit??100)));if(!Number.isFinite(limit))throw new ApiError('Invalid record limit.');
  let query='SELECT * FROM research_records WHERE user_id=?';const args:(string|number)[]=[userId];
  if(options.kind){query+=' AND kind=?';args.push(options.kind);}if(options.entityKey){query+=' AND entity_key=?';args.push(options.entityKey);}query+=' ORDER BY observed_at DESC,created_at DESC LIMIT ?';args.push(limit);
  return(getDb().prepare(query).all(...args) as Record<string,any>[]).map(recordRow);
}
export function getResearchRecord(userId:string,id:string){const row=getDb().prepare('SELECT * FROM research_records WHERE id=? AND user_id=?').get(id,userId) as Record<string,any>|undefined;if(!row)throw new ApiError('Research record not found.',404);return recordRow(row);}
export function deleteResearchRecord(userId:string,id:string){const result=getDb().prepare('DELETE FROM research_records WHERE id=? AND user_id=?').run(id,userId);if(!result.changes)throw new ApiError('Research record not found.',404);}
