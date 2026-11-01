import {MongoClient,type Db} from 'mongodb';
import {verifyResearchDocument,type ResearchDocument} from './schema';

let pending:Promise<Db>|undefined;
let repository:Promise<MongoResearchRepository>|undefined;
export function mongoConfigured(){return process.env.GRIDIRON_MONGODB_RESEARCH==='1'&&Boolean(process.env.MONGODB_URI&&process.env.MONGODB_DATABASE);}
export async function mongoDatabase():Promise<Db>{
 if(!mongoConfigured())throw Error('MongoDB research storage is not configured.');
 if(!pending)pending=(async()=>{const uri=process.env.MONGODB_URI!;if(!uri.startsWith('mongodb+srv://')||/tls=false|ssl=false|tlsInsecure=true|tlsAllowInvalid/i.test(uri))throw Error('Atlas requires a verified TLS SRV connection.');
  // A personal app on serverless Vercel: short document operations, one shared
  // client per warm instance, three sockets maximum and no idle minimum.
  const client=new MongoClient(uri,{maxPoolSize:3,minPoolSize:0,maxIdleTimeMS:30000,serverSelectionTimeoutMS:5000,connectTimeoutMS:5000,socketTimeoutMS:15000,waitQueueTimeoutMS:3000,compressors:['zlib'],retryWrites:true,appName:'GRIDIRON-AI-research'});
  try{await client.connect();return client.db(process.env.MONGODB_DATABASE);}catch{await client.close();throw Error('Atlas research connection unavailable.');}
 })().catch(error=>{pending=undefined;throw error;});return pending;
}
export class MongoResearchRepository{
 constructor(private db:Db){}
 private collection(){return this.db.collection<ResearchDocument>('research_documents');}
 async ensureIndexes(){const exists=await this.db.listCollections({name:'research_documents'},{nameOnly:true}).hasNext();if(!exists)try{await this.db.createCollection('research_documents',{validator:{$jsonSchema:{bsonType:'object',required:['_id','schemaVersion','sport','gameId','kind','modelVersion','createdAt','sha256','bytes','payload'],properties:{_id:{bsonType:'string',pattern:'^[a-f0-9]{64}$'},schemaVersion:{enum:[1]},sport:{enum:['NFL','CFB']},gameId:{bsonType:'string'},kind:{enum:['simulation','injury_snapshot','matchup_report','explanation','source_metadata']},modelVersion:{bsonType:['string','null']},createdAt:{bsonType:'string'},sha256:{bsonType:'string',pattern:'^[a-f0-9]{64}$'},bytes:{bsonType:['int','long','double'],minimum:0,maximum:2000000},payload:{bsonType:'object'}},additionalProperties:false}},validationLevel:'strict',validationAction:'error'});}catch(error:any){if(error?.code!==48)throw Error('Research collection initialization failed. Existing collections were preserved.');}const existing=await this.collection().findOne({},{projection:{schemaVersion:1}});if(existing&&existing.schemaVersion!==1)throw Error('Existing research collection has an unsupported schema; no records were changed.');await this.collection().createIndexes([{key:{sport:1,gameId:1,createdAt:-1,_id:-1},name:'sport_game_history'}]);}
 async put(document:ResearchDocument){verifyResearchDocument(document,document._id,document.sha256);await this.collection().updateOne({_id:document._id},{$setOnInsert:document},{upsert:true});const stored=await this.collection().findOne({_id:document._id});if(!stored)throw Error('Atlas did not acknowledge the research document.');verifyResearchDocument(stored,document._id,document.sha256);return{acknowledged:true,id:stored._id,sha256:stored.sha256};}
 async get(id:string,sha256:string){if(!/^[a-f0-9]{64}$/.test(id)||!/^[a-f0-9]{64}$/.test(sha256))throw Error('Invalid research identity.');const document=await this.collection().findOne({_id:id},{maxTimeMS:5000});return document?verifyResearchDocument(document,id,sha256):null;}
 async page(sport:'NFL'|'CFB',gameId:string,cursor?:{createdAt:string;id:string},limit=20){const query:any={sport,gameId};if(cursor)query.$or=[{createdAt:{$lt:cursor.createdAt}},{createdAt:cursor.createdAt,_id:{$lt:cursor.id}}];const rows=await this.collection().find(query,{projection:{payload:0},maxTimeMS:5000}).sort({createdAt:-1,_id:-1}).limit(Math.max(1,Math.min(limit,100))).toArray();return{rows,next:rows.length?{createdAt:rows.at(-1)!.createdAt,id:rows.at(-1)!._id}:null};}
 async usage(){const stats=await this.db.stats({scale:1});return{dataBytes:stats.dataSize,storageBytes:stats.storageSize,indexBytes:stats.indexSize,collections:stats.collections,objects:stats.objects,scope:'Configured research database; not account billing.'};}
}
export async function mongoResearch(){return repository??=mongoDatabase().then(async db=>{const value=new MongoResearchRepository(db);await value.ensureIndexes();return value;}).catch(error=>{repository=undefined;throw error;});}
