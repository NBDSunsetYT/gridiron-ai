import {createHash,randomUUID} from 'node:crypto';
import {z} from 'zod';
import {ApiError} from '../auth';
import {valueContract,validateQuote,validateSimulationSettlement,injuryChanges,performanceHistory,type ContractQuote} from '../contracts';
import {injurySchema,availabilityScenario,authoritativeUrl} from '../injuries';
import {wilson} from '../model';
import {type CloudContext,cloudError,requireCloudUser} from './context';
import {records,allRecords,record,saveRecord,updateRecord,unwrap} from './store';
import {verifyCloudResult} from './attestation';
import {contractUncertainty} from '../uncertainty';

export async function cloudContracts(ctx:CloudContext){
 const [qr,pr,sr,ir,pp]=await Promise.all(['contract_quotes','prediction_snapshots','contract_settlements','injury_history','paper_positions'].map(k=>allRecords(ctx,k)));
 const quotes=unwrap(qr) as ContractQuote[],predictions=unwrap(pr),settlements=unwrap(sr),injuries=unwrap(ir),paper=unwrap(pp);
 const annotated=predictions.map(p=>{const changed=injuryChanges(p.injuryVersions??[],injuries),q=quotes.find(q=>q.id===p.quoteId);return{...p,stale:!!p.stale||changed.length>0||!!q&&Date.now()-Date.parse(q.quotedAt)>120000,injuryChanges:changed.map(i=>i.id)};});
 const seen=new Set<string>(),contracts=quotes.filter(q=>{if(seen.has(q.contractId))return false;seen.add(q.contractId);return true;}).map(q=>({...q,stale:Date.now()-Date.parse(q.quotedAt)>120000,executable:false}));
 return{contracts,quotes,predictions:annotated,settlements,paperPositions:paper.map(p=>{const s=settlements.find(s=>s.contractId===p.contractId);return{...p,status:s?'settled':'open',realizedProfitCents:s?(s.outcome===(p.side==='YES'?1:0)?p.valuation.winNetProfitCents:p.valuation.lossNetProfitCents):null};}),performance:performanceHistory(quotes,predictions,settlements),provider:{name:'DraftKings Predictions',status:'unavailable',message:'No authorized direct Predictions feed is configured. Exact binary contracts are user-verified manual snapshots. No actual executable fills or prices are assumed.'}};
}
export async function cloudSaveQuote(ctx:CloudContext,input:unknown){
 const quote=validateQuote(input),previous=unwrap(await records(ctx,'contract_quotes',{entityKey:quote.contractId}));
 for(const p of previous){for(const key of ['eventId','threshold','operator','eventStart','settlementRule'])if(p[key]!==quote[key as keyof ContractQuote])throw new ApiError('An established contract identifier cannot change event or settlement rules.');if(p.settlementDefinition&&JSON.stringify(p.settlementDefinition)!==JSON.stringify(quote.settlementDefinition))throw new ApiError('The structured settlement definition is immutable.');}
 await saveRecord(ctx,'contract_quotes',quote,{id:quote.id,entityKey:quote.contractId,source:quote.sourceUrl,observedAt:quote.quotedAt});return quote;
}
const predictionInput=z.object({quoteId:z.string().uuid(),probability:z.number().gt(0).lt(1),side:z.enum(['YES','NO']),quantity:z.number().int().min(1).max(100000),asOf:z.string().datetime({offset:true}),inputsHash:z.string().min(8).max(200),modelVersion:z.string().min(3).max(200).default('supplied-estimate-v1'),supersedesPredictionId:z.string().uuid().optional(),injuryEntityKeys:z.array(z.string()).max(100).default([]),evidence:z.object({source:z.string().min(3).max(1000),method:z.string().min(3).max(2000),sampleSize:z.number().int().min(20),simulationId:z.string().uuid().optional(),outcomes:z.array(z.boolean()).min(20).max(100000).optional()})});
export async function cloudSavePrediction(ctx:CloudContext,input:unknown){
 const p=predictionInput.parse(input),quote=(await record(ctx,p.quoteId,'contract_quotes')).data as ContractQuote,now=new Date().toISOString();p.asOf=new Date(p.asOf).toISOString();
 if(Date.parse(p.asOf)>=Date.parse(quote.eventStart)||Date.parse(p.asOf)>Date.now()+60000||Date.parse(quote.quotedAt)>Date.parse(p.asOf))throw new ApiError('Forecast as-of time must precede event start and cannot use later quotes or future data.');
 if(p.supersedesPredictionId){const previous=await record(ctx,p.supersedesPredictionId,'prediction_snapshots');if(previous.data.contractId!==quote.contractId)throw new ApiError('Superseded snapshot must belong to the same contract.');}
 const injuries=unwrap(await allRecords(ctx,'injury_history'));
 const injuryVersions=p.injuryEntityKeys.map(entityKey=>{const i=injuries.filter(i=>i.entityKey===entityKey&&Date.parse(i.checkedAt)<=Date.parse(p.asOf)).sort((a,b)=>Date.parse(b.checkedAt)-Date.parse(a.checkedAt))[0];if(!i)throw new ApiError('A declared injury lacks evidence available before the forecast cutoff.');return{entityKey,id:i.id,factsHash:i.factsHash,publicationAt:i.publicationAt,checkedAt:i.checkedAt,staleAtCapture:Date.parse(p.asOf)-Date.parse(i.checkedAt)>86400000||Date.parse(p.asOf)-Date.parse(i.publicationAt)>259200000};});
 let probability=p.evidence.outcomes?(p.evidence.outcomes.filter(Boolean).length+.5)/(p.evidence.outcomes.length+1):p.probability,sourceValidation=p.evidence.outcomes?'calculated_from_submitted_outcomes':'user_supplied_model_estimate_not_independently_verified';
 let probabilityUncertainty:Record<string,any>={modelInterval:null,method:'Externally supplied estimate; total model uncertainty is unavailable.'};
 if(p.evidence.outcomes){p.evidence.sampleSize=p.evidence.outcomes.length;probabilityUncertainty={samplingInterval:wilson(p.evidence.outcomes.filter(Boolean).length,p.evidence.outcomes.length),modelInterval:null};}
 if(p.evidence.simulationId){const saved=await record(ctx,p.evidence.simulationId,'simulation_jobs'),job=saved.data,result=job.result;if(job.status!=='completed'||!result)throw new ApiError('A completed owned simulation is required.');verifyCloudResult(ctx,p.evidence.simulationId,job);const c=result.contracts?.find((c:any)=>c.id===quote.contractId);if(!c)throw new ApiError('No exact contract identifier exists in the saved simulation.');validateSimulationSettlement(quote,c,result);
  if(Date.parse(result.evidenceCutoff)>Date.parse(p.asOf)||Date.parse(saved.created_at)>Date.parse(p.asOf)||Date.parse(result.eventStart)!==Date.parse(quote.eventStart))throw new ApiError('Simulation evidence/capture and event timestamps must agree with the quote.');
  if(!Number.isFinite(c.probability)||c.probability<=0||c.probability>=1)throw new ApiError('Finite tail evidence is insufficient for a boundary probability.');
  probability=c.probability;p.modelVersion=result.modelVersion;p.evidence.sampleSize=result.simulations;sourceValidation='calculated_from_completed_simulation';probabilityUncertainty=contractUncertainty(result,quote.contractId);
 }
 const result={...p,id:randomUUID(),kind:'binary_contract',contractId:quote.contractId,eventStart:quote.eventStart,yesProbability:probability,probability:p.side==='YES'?probability:1-probability,valuation:valueContract(quote,probability,p.side,p.quantity),injuryVersions,computedInputsHash:createHash('sha256').update(JSON.stringify({quoteId:quote.id,evidence:p.evidence,injuryVersions,asOf:p.asOf,modelVersion:p.modelVersion})).digest('hex'),sourceValidation,probabilityUncertainty,auditStatus:Date.parse(now)<Date.parse(quote.eventStart)&&Date.parse(quote.createdAt)<Date.parse(quote.eventStart)&&Math.abs(Date.parse(now)-Date.parse(p.asOf))<=120000?'prospective':'retrospective_import',stale:Date.parse(p.asOf)-Date.parse(quote.quotedAt)>120000||injuryVersions.some(i=>i.staleAtCapture),createdAt:now};
 await saveRecord(ctx,'prediction_snapshots',result,{entityKey:quote.contractId,observedAt:p.asOf});return result;
}
export async function cloudSettleContract(ctx:CloudContext,input:unknown){
 const p=z.object({contractId:z.string(),quoteId:z.string().uuid(),predictionId:z.string().uuid(),outcome:z.union([z.literal(0),z.literal(1)]),settledAt:z.string().datetime({offset:true}),sourceUrl:z.string().url(),verified:z.literal(true)}).parse(input),prediction=(await record(ctx,p.predictionId,'prediction_snapshots')).data;
 if(prediction.contractId!==p.contractId||prediction.quoteId!==p.quoteId)throw new ApiError('Settlement must reference the same quote, contract and prediction.');
 if(Date.parse(p.settledAt)<Date.parse(prediction.eventStart)||Date.parse(p.settledAt)>Date.now()+60000)throw new ApiError('Settlement must follow event start and cannot be in the future.');
 if((await records(ctx,'contract_settlements',{entityKey:p.contractId})).length)throw new ApiError('An immutable settlement already exists.',409);
 const result={...p,id:randomUUID(),createdAt:new Date().toISOString(),verification:'manual_user_verified'};await saveRecord(ctx,'contract_settlements',result,{entityKey:p.contractId,source:p.sourceUrl,observedAt:p.settledAt});return result;
}
export async function cloudPaper(ctx:CloudContext,input:unknown){
 const p=z.object({predictionId:z.string().uuid()}).parse(input),prediction=(await record(ctx,p.predictionId,'prediction_snapshots')).data;
 if(Date.parse(prediction.eventStart)<=Date.now())throw new ApiError('Paper entries must be captured before event start.');
 const result={id:randomUUID(),predictionId:p.predictionId,contractId:prediction.contractId,side:prediction.side,quantity:prediction.quantity,valuation:prediction.valuation,recordedAt:new Date().toISOString(),pricing:'hypothetical_snapshot_price_not_verified_fill'};await saveRecord(ctx,'paper_positions',result,{entityKey:prediction.contractId});return result;
}
export async function cloudInjuries(ctx:CloudContext){const history=unwrap(await allRecords(ctx,'injury_history')),seen=new Set<string>();return{history,records:history.filter(i=>{if(seen.has(i.entityKey))return false;seen.add(i.entityKey);return true;}).map(i=>({...i,stale:Date.now()-Date.parse(i.checkedAt)>86400000||Date.now()-Date.parse(i.publicationAt)>259200000})),sources:[{name:'Official / licensed reports',status:'manual_verification',message:'Citations are user verified, not an independently fetched injury wire.'}],policy:'No numerical availability probability is invented without sufficient documented cohort evidence.'};}
export async function cloudSaveInjury(ctx:CloudContext,input:unknown){
 const owner=requireCloudUser(ctx);
 // Retain actual practice evidence instead of silently stripping it during parsing.
 const p=injurySchema.extend({practiceParticipation:z.enum(['full','limited','did_not_participate','not_reported','unknown']).optional()}).parse(input);p.checkedAt=new Date(p.checkedAt).toISOString();p.publicationAt=new Date(p.publicationAt).toISOString();
 if(p.sourceType==='official'&&!authoritativeUrl(p.sourceUrl))throw new ApiError('Official reports require an HTTPS NFL/team source.');
 if(Date.parse(p.publicationAt)>Date.parse(p.checkedAt)||Date.parse(p.checkedAt)>Date.now()+60000)throw new ApiError('Invalid publication/check chronology.');
 if(p.cohorts&&(Date.parse(p.cohorts.asOf)>Date.parse(p.checkedAt)||p.cohorts.active+p.cohorts.limited+p.cohorts.out<20))throw new ApiError('Availability cohorts need 20 comparable historical outcomes available before the check.');
 const history=unwrap(await records(ctx,'injury_history',{entityKey:p.entityKey})),previous=history[0];if(previous&&Date.parse(p.checkedAt)<Date.parse(previous.checkedAt))throw new ApiError('New current reports cannot predate the existing check.');
 // Preserve existing hashes when no practice evidence was supplied.
 const factsHash=createHash('sha256').update(JSON.stringify({status:p.status,note:p.note,cohorts:p.cohorts??null,...(p.practiceParticipation===undefined?{}:{practiceParticipation:p.practiceParticipation})})).digest('hex');
 const stableId=(kind:string,identity:unknown)=>{const hash=createHash('sha256').update(JSON.stringify(['injury-reconciliation-v1',owner.id,p.entityKey,kind,identity])).digest('hex');return `${hash.slice(0,8)}-${hash.slice(8,12)}-5${hash.slice(13,16)}-a${hash.slice(17,20)}-${hash.slice(20,32)}`;};
 // Inserts only: conflict recovery reads the existing owned record and never resets
 // a completed/running job or overwrites an immutable evidence snapshot.
 const insertOnce=async(kind:string,value:Record<string,any>,options:{entityKey?:string;source?:string;observedAt?:string}={}):Promise<Record<string,any>>=>{
  try{return await saveRecord(ctx,kind,value,{...options,id:value.id});}catch(error){if(!(error instanceof ApiError)||error.status!==409)throw error;const existing=await record(ctx,value.id,kind);return {...existing.data,id:existing.id,createdAt:existing.created_at};}
 };
 const sameEvidence=history.find(h=>Object.entries(p).every(([key,value])=>JSON.stringify(h[key])===JSON.stringify(value)));
 const result=sameEvidence??await insertOnce('injury_history',{...p,id:stableId('evidence',p),factsHash,availability:availabilityScenario(p),verification:'manual_user_attested',createdAt:new Date().toISOString()},{entityKey:p.entityKey,source:p.sourceUrl,observedAt:p.checkedAt});
 const [predictions,jobs,notices]=await Promise.all(['prediction_snapshots','simulation_jobs','notification_history'].map(kind=>allRecords(ctx,kind).then(unwrap)));
 const relatedEvidence=new Map([...history,result].map(h=>[h.id,h]));
 const sameFacts=(entry:Record<string,any>,predictionId:string)=>{const d=entry.data??entry;return d.predictionId===predictionId&&(d.factsHash===factsHash||relatedEvidence.get(d.injuryRecordId)?.factsHash===factsHash)&&d.entityKey===p.entityKey;};
 const affected:string[]=[],queued=new Set<string>();
 // Always reconcile. A previous save may have committed evidence but failed before
 // its notification or job insert. An identical retry must repair either gap.
 for(const prediction of predictions){if(!(prediction.injuryEntityKeys??[]).includes(p.entityKey)||Date.parse(prediction.eventStart)<=Date.now()||queued.has(prediction.contractId))continue;queued.add(prediction.contractId);
  if((prediction.injuryVersions??[]).some((i:any)=>i.entityKey===p.entityKey&&i.factsHash===factsHash))continue;
  affected.push(prediction.id);const identity=[factsHash,prediction.id];
  if(!notices.some(n=>n.type==='prediction_stale'&&sameFacts(n,prediction.id)))await insertOnce('notification_history',{id:stableId('notification',identity),type:'prediction_stale',predictionId:prediction.id,injuryRecordId:result.id,entityKey:p.entityKey,factsHash,reason:'Referenced injury evidence changed; old snapshots are stale until reviewed or rerun.',createdAt:new Date().toISOString(),delivery:'in_app_only'});
  if(jobs.some(j=>j.kind==='injury_resimulation'&&sameFacts(j,prediction.id)))continue;
  const source=prediction.evidence?.simulationId,inputs=source?(await records(ctx,'simulation_inputs',{entityKey:source,limit:1}))[0]:null,now=new Date().toISOString();
  await insertOnce('simulation_jobs',{id:stableId('job',identity),kind:'injury_resimulation',status:inputs?'queued':'blocked',data:{sourceJobId:source,predictionId:prediction.id,injuryRecordId:result.id,entityKey:p.entityKey,factsHash},error:inputs?null:'Original signed simulation input is unavailable.',createdAt:now,updatedAt:now});
 }
 return{record:result,affectedPredictionIds:affected,resimulationRequired:affected.length};
}

export async function cloudConversations(ctx:CloudContext){const u=requireCloudUser(ctx),{data,error}=await ctx.client.from('conversations').select('*').eq('user_id',u.id).order('updated_at',{ascending:false}).limit(100);if(error)cloudError(error);return(data??[]).map(c=>({id:c.id,title:c.title,createdAt:c.created_at,updatedAt:c.updated_at}));}
export async function cloudConversation(ctx:CloudContext,id:string){
 const u=requireCloudUser(ctx),{data,error}=await ctx.client.from('conversations').select('*').eq('user_id',u.id).eq('id',id).maybeSingle();
 if(error)cloudError(error);if(!data)throw new ApiError('Conversation not found.',404);
 const messages:Record<string,any>[]=[];let offset=0,expected:number|null=null,bytes=0;
 for(;;){
  const page=await ctx.client.from('conversation_messages').select('*',{count:'exact'}).eq('user_id',u.id).eq('conversation_id',id).order('created_at',{ascending:true}).order('id',{ascending:true}).range(offset,offset+999);
  if(page.error)cloudError(page.error);
  if(typeof page.count!=='number')throw new ApiError('Complete conversation history could not be verified. No partial history was used.',503);
  if(expected===null)expected=page.count;else if(page.count!==expected)throw new ApiError('Conversation changed during retrieval. Retry to load the current history.',409);
  const rows=page.data??[];bytes+=Buffer.byteLength(JSON.stringify(rows),'utf8');
  if(bytes>40_000_000)throw new ApiError('Complete conversation history exceeds this interactive request bound. Export the account to recover every message; no partial history was used.',413);
  messages.push(...rows);offset+=rows.length;
  if(offset===expected)break;
  if(!rows.length||offset>expected)throw new ApiError('Conversation pagination could not reconcile every saved message. Retry before using this history.',409);
 }
 return{id:data.id,title:data.title,createdAt:data.created_at,updatedAt:data.updated_at,messages:messages.map(m=>({id:m.id,role:m.role as 'user'|'assistant',content:m.content,data:m.data,createdAt:m.created_at}))};
}
export async function cloudCreateConversation(ctx:CloudContext,title='New research conversation'){const u=requireCloudUser(ctx);if(typeof title!=='string'||!title.trim()||title.length>200)throw new ApiError('Conversation title must contain 1–200 characters.');const row={id:randomUUID(),user_id:u.id,title:title.trim(),created_at:new Date().toISOString(),updated_at:new Date().toISOString()},{error}=await ctx.client.from('conversations').insert(row);if(error)cloudError(error);return{id:row.id,title:row.title,createdAt:row.created_at,updatedAt:row.updated_at};}
export async function cloudAppendMessage(ctx:CloudContext,id:string,input:any){await cloudConversation(ctx,id);const p=z.object({role:z.enum(['user','assistant']),content:z.string().min(1).max(40000),data:z.record(z.string(),z.unknown()).optional()}).parse(input),u=requireCloudUser(ctx),row={id:randomUUID(),conversation_id:id,user_id:u.id,...p,data:p.data??{},created_at:new Date().toISOString()},{error}=await ctx.client.from('conversation_messages').insert(row);if(error)cloudError(error);const update=await ctx.client.from('conversations').update({updated_at:row.created_at}).eq('user_id',u.id).eq('id',id);if(update.error)cloudError(update.error);return{id:row.id,role:row.role,content:row.content,data:row.data,createdAt:row.created_at};}
