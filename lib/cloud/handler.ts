import {randomUUID,createHash} from 'node:crypto';
import {after} from 'next/server';
import {z} from 'zod';
import {ApiError,errorResponse,guardMutation,readJsonObject,requestOrigin} from '../auth';
import {moneyToCents,SPORTSBOOKS} from '../ledger';
import {encryptBackup,decryptBackup} from '../backups';
import {distribution,parlay} from '../model';
import {TheOddsApi,providerStatuses,ProviderError,type Market} from '../providers';
import {simulationParlay} from '../simulation-parlay';
import {cloudContext,cloudConfiguration,CloudAuthUnavailable,authUnavailable,requireCloudUser,ensureProfile,setCloudSession,clearCloudSession,finishCloud,forwardCloudRequest,cloudRateLimit,rpc,cloudError,type CloudContext} from './context';
import {records,record,saveRecord,updateRecord,deleteRecord,unwrap,preferences,updatePreferences,finiteJson} from './store';
import {cloudContracts,cloudSaveQuote,cloudSavePrediction,cloudSettleContract,cloudPaper,cloudInjuries,cloudSaveInjury,cloudConversations,cloudConversation,cloudCreateConversation,cloudAppendMessage} from './research';
import {cloudRunSimulation,cloudSimulationHistory,cloudJobHistory,cloudProcessJobs} from './simulations';
import {verifyCloudResult,verifiedCloudJob} from './attestation';
import {cloudImportContracts} from './imports';
import {exportOwnedTables,OWNED_TYPED_EXPORT_TABLES} from './export';
import {decodeCloudData} from './codec';

const json=(data:unknown,status=200)=>Response.json(data,{status});
const publicLimits=new Map<string,{count:number;until:number}>();
function limitAuth(request:Request){const key=createHash('sha256').update(request.headers.get('x-forwarded-for')?.split(',')[0]??'local').digest('hex'),now=Date.now();for(const[k,v]of publicLimits)if(v.until<now)publicLimits.delete(k);const previous=publicLimits.get(key);if(previous&&previous.count>=30)throw new ApiError('Too many authentication requests. Try again later.',429);if(publicLimits.size>10000)throw new ApiError('Authentication is busy. Try again later.',429);publicLimits.set(key,{count:(previous?.count??0)+1,until:previous?.until??now+900000});}
export async function cloudSettings(ctx:CloudContext){const u=requireCloudUser(ctx),{data,error}=await ctx.client.from('profiles').select('settings').eq('user_id',u.id).single();if(error)cloudError(error);return data.settings??{monthlyLimitCents:null,timezone:'UTC',notifications:{},theme:'dark'};}
async function auth(ctx:CloudContext,request:Request){
 if(request.method==='GET')return json({user:ctx.user?{id:ctx.user.id,email:ctx.user.email}:null,backend:'supabase'});
 if(request.method!=='POST')throw new ApiError('Method not supported.',405);
 guardMutation(request);limitAuth(request);const input=await readJsonObject(request);
 if(input.action==='logout'){if(ctx.accessToken){const config=cloudConfiguration();let response:Response;try{response=await fetch(config.url+'/auth/v1/logout?scope=local',{method:'POST',headers:{apikey:config.key,Authorization:`Bearer ${ctx.accessToken}`},signal:AbortSignal.timeout(15000)});}catch{throw new ApiError('Supabase sign-out could not be verified. Retry before leaving a shared device.',503);}if(!response.ok&&response.status!==401)throw new ApiError('Supabase sign-out failed. Retry before leaving a shared device.',503);}clearCloudSession(ctx);return json({user:null});}
 const values=z.object({email:z.string().email().max(254),password:z.string().min(12).max(128)}).parse(input);
 const response=input.action==='register'?await ctx.client.auth.signUp({email:values.email,password:values.password,options:{emailRedirectTo:requestOrigin(request)}}):input.action==='login'?await ctx.client.auth.signInWithPassword(values):null;
 if(!response)throw new ApiError('Choose register, login or logout.');
 if(response.error){if(authUnavailable(response.error))throw new ApiError('Supabase authentication could not be reached. Your credentials were not rejected; retry when the provider connection is available.',503);throw new ApiError(response.error.status===429?'Supabase authentication rate limit reached. Please try later.':input.action==='login'?'Email/password are incorrect or email verification is incomplete.':response.error.message.slice(0,350),response.error.status===429?429:400);}
 if(!response.data.session)return json({user:null,confirmationRequired:true,message:'Check your email to confirm this account, then sign in. No signed-in session has been created.'},202);
 const verified=await ctx.client.auth.getUser(response.data.session.access_token);if(verified.error||!verified.data.user)throw new ApiError('Supabase could not verify the new session.',503);
 ctx.user=verified.data.user;setCloudSession(ctx,response.data.session);await ensureProfile(ctx);return json({user:{id:ctx.user.id,email:ctx.user.email},backend:'supabase'});
}
async function inputBody(request:Request,max=1_000_000){
 if(max===1_000_000){guardMutation(request);return readJsonObject(request);}
 const origin=request.headers.get('origin');if(origin&&origin!==requestOrigin(request))throw new ApiError('Cross-origin requests are not allowed.',403);
 if(!/^application\/json(?:;|$)/i.test(request.headers.get('content-type')??''))throw new ApiError('Use application/json.',415);
 const reader=request.body?.getReader();if(!reader)throw new ApiError('JSON object required.');let count=0;const chunks:Uint8Array[]=[];for(;;){const{done,value}=await reader.read();if(done)break;count+=value.length;if(count>max){await reader.cancel();throw new ApiError('Request exceeds the supported evidence size.',413);}chunks.push(value);}
 const value=JSON.parse(Buffer.concat(chunks).toString('utf8'));if(!value||typeof value!=='object'||Array.isArray(value))throw new ApiError('JSON object required.');return value as Record<string,any>;
}
function csvValue(value:unknown){let text=String(value??'');if(/^[=+@\-\t\r]/.test(text))text="'"+text;return'"'+text.replaceAll('"','""')+'"';}
const manualMarket=z.object({event:z.string().min(3).max(180),selection:z.string().min(1).max(140),market:z.string().min(2).max(100),line:z.number().finite().optional(),odds:z.number().finite().refine(v=>Math.abs(v)>=100&&Math.abs(v)<=100000),sportsbook:z.enum(['DraftKings','Hard Rock','Other']),observedAt:z.string().datetime().optional(),sourceUrl:z.string().url().optional(),provenance:z.string().max(1000).optional(),samples:z.array(z.number().finite()).min(20).max(10000).optional(),direction:z.enum(['over','under']).optional()});
async function markets(ctx:CloudContext,request:Request,payload?:any){
 if(request.method==='GET'){const markets=unwrap(await records(ctx,'markets'));return json({markets,providers:providerStatuses(markets as Market[])});}
 const input=payload??await inputBody(request);let values:Market[];
 if(input.action==='refresh')values=await new TheOddsApi(process.env.ODDS_API_KEY??'').fetchMarkets();else values=z.array(manualMarket).min(1).max(500).parse(input.markets??[input]).map(m=>{if(m.observedAt&&Date.parse(m.observedAt)>Date.now()+60000)throw new ApiError('Observed prices cannot be in the future.');if(m.samples&&(!m.provenance||m.line===undefined||!m.direction))throw new ApiError('Outcome samples require a source, threshold and direction.');return{...m,id:randomUUID(),source:'manual',observedAt:m.observedAt??new Date().toISOString(),sampleSize:m.samples?.length??0,model:m.samples?distribution(m.samples,m.line!,m.direction!,m.odds):undefined} as Market;});
 const u=requireCloudUser(ctx);const rows=values.map(v=>({id:v.id,user_id:u.id,kind:'markets',entity_key:v.eventId??v.event,data:finiteJson(v),source:v.sourceUrl??v.provider??'manual',observed_at:v.observedAt}));if(rows.length){const result=await ctx.client.from('gridiron_records').insert(rows);if(result.error)cloudError(result.error);}
 return json({markets:unwrap(await records(ctx,'markets')),imported:values.length,message:values.length?'Snapshots stored in your Supabase account.':'No supported authorized prices were returned. No replacements were invented.'});
}
async function exportCloud(ctx:CloudContext,password:string){
 const user=requireCloudUser(ctx),rawLedger=await rpc(ctx,'gridiron_export_financial'),ledger=await rpc(ctx,'gridiron_ledger'),settings=await cloudSettings(ctx),prefs=await preferences(ctx);
 if(rawLedger.journal.length!==ledger.transactions.length||rawLedger.bets.length!==ledger.bets.length)throw new ApiError('Account changed while the export was assembled. Retry to capture a consistent financial snapshot.',409);
 const cash=rawLedger.postings.filter((r:any)=>['cash','escrow'].includes(r.account)).reduce((n:number,r:any)=>n+Number(r.amount_cents),0);
 if(!Number.isSafeInteger(cash)||cash!==ledger.summary.cashBalanceCents)throw new ApiError('Financial export reconciliation failed. Retry or use a consistent project-level backup.',409);
 const exported=await exportOwnedTables(ctx,['gridiron_records','conversations','conversation_messages',...OWNED_TYPED_EXPORT_TABLES]);
 const research:Record<string,any>={typedTables:Object.fromEntries(OWNED_TYPED_EXPORT_TABLES.map(table=>[table,exported[table]]))};
 let expandedBytes=Buffer.byteLength(JSON.stringify(research),'utf8');
 for(const stored of exported.gridiron_records){const row:Record<string,any>={...stored,data:decodeCloudData(stored.data)};let kind=row.kind,value:any={...row};if(kind.startsWith('research_records/')){kind='research_records';value.kind=row.kind.slice('research_records/'.length);value.data=row.data?._recordFormat==='saved-research-v1'?row.data.value:row.data;}else if(kind==='simulation_jobs'){value={...row,...row.data,data:row.data.data,result:row.data.result,status:row.data.status,kind:row.data.kind};}else if(kind==='simulation_inputs'){value={...row,job_id:row.data.jobId,data:row.data.input};}expandedBytes+=Buffer.byteLength(JSON.stringify(value),'utf8');if(expandedBytes>60_000_000)throw new ApiError('The complete expanded account export exceeds the interactive 60 MB recovery bound. No partial backup was returned; use a consistent project backup.',413);(research[kind]??=[]).push(value);}
 research.conversations=exported.conversations;research.conversation_messages=exported.conversation_messages;
 const backup={version:2,backend:'supabase',createdAt:new Date().toISOString(),email:user.email,ledger,rawLedger,settings,preferences:prefs,research,limitations:['Raw financial data is reconciled and all owned typed tables are included. Typed warehouse/model restoration is archived in the imported source payload until a dedicated typed restore operation is implemented. Consistent full PostgreSQL recovery still requires project backups. Authentication secrets are excluded.']};
 if(Buffer.byteLength(JSON.stringify(backup),'utf8')>60_000_000)throw new ApiError('The complete expanded account export exceeds the interactive 60 MB recovery bound. No partial backup was returned; use a consistent project backup.',413);
 return encryptBackup(backup,password);
}

export async function handleCloudRequest(request:Request,pathParts:string[]){
 let ctx:CloudContext|undefined;
 try{
  ctx=await cloudContext(request);const path=pathParts.join('/'),method=request.method,query=new URL(request.url).searchParams;
  if(path==='auth')return finishCloud(ctx,await auth(ctx,request));
  const user=requireCloudUser(ctx);await ensureProfile(ctx);
  if(method!=='GET'){const origin=request.headers.get('origin');if(origin&&origin!==requestOrigin(request))throw new ApiError('Cross-origin requests are not allowed.',403);if(!/^application\/json(?:;|$)/i.test(request.headers.get('content-type')??''))throw new ApiError('Use application/json.',415);await cloudRateLimit(ctx,path,path==='assistant'?12:path==='simulations'?12:path==='quant'?6:60,['simulations','quant'].includes(path)?3600000:60000);}
  let result:Response;
  if(path==='ledger'){
   result=method==='GET'?json(await rpc(ctx,'gridiron_ledger')):method==='POST'?json(await rpc(ctx,'gridiron_post_transaction',await inputBody(request)),201):method==='PUT'?json(await rpc(ctx,'gridiron_reverse_transaction',await inputBody(request))):json({error:'Method not supported.'},405);
  }else if(path==='bets'){
   const p=await inputBody(request);result=json(await rpc(ctx,p.action==='settle'?'gridiron_settle_bet':p.action==='place'?'gridiron_place_bet':(()=>{throw new ApiError('Choose place or settle.');})(),p),201);
  }else if(path==='account'){
   if(method==='GET')result=json({user:{id:user.id,email:user.email},settings:await cloudSettings(ctx),capabilities:{passkeys:false,notifications:false},backend:'supabase'});
   else if(method==='PATCH')result=json({settings:await rpc(ctx,'gridiron_update_settings',await inputBody(request))});
   else if(method==='DELETE'){const p=await inputBody(request);if(p.confirmation!=='DELETE')throw new ApiError('Type DELETE to confirm deletion.');const response=await ctx.client.functions.invoke('delete-account',{body:{confirmation:'DELETE'}});if(response.error)throw new ApiError('Account deletion requires the deployed authenticated delete-account Edge Function. No data was reset locally.',503);clearCloudSession(ctx);result=json({deleted:true});}
   else throw new ApiError('Method not supported.',405);
  }else if(path==='preferences')result=method==='GET'?json({preferences:await preferences(ctx)}):json({preferences:await updatePreferences(ctx,(await inputBody(request)).preferences)});
  else if(path==='conversations')result=method==='GET'?json({conversations:await cloudConversations(ctx)}):json({conversation:await cloudCreateConversation(ctx,(await inputBody(request)).title)},201);
  else if(pathParts[0]==='conversations'&&pathParts.length===2){const id=pathParts[1];
   if(method==='GET')result=json({conversation:await cloudConversation(ctx,id)});
   else if(method==='POST')result=json({message:await cloudAppendMessage(ctx,id,await inputBody(request))},201);
   else if(method==='PATCH'){const p=await inputBody(request);await cloudConversation(ctx,id);if(typeof p.title!=='string'||!p.title.trim()||p.title.length>200)throw new ApiError('Valid title required.');const r=await ctx.client.from('conversations').update({title:p.title.trim(),updated_at:new Date().toISOString()}).eq('user_id',user.id).eq('id',id);if(r.error)cloudError(r.error);result=json({conversation:await cloudConversation(ctx,id)});}
   else if(method==='DELETE'){guardMutation(request);await cloudConversation(ctx,id);const r=await ctx.client.from('conversations').delete().eq('user_id',user.id).eq('id',id);if(r.error)cloudError(r.error);result=json({deleted:true});}
   else throw new ApiError('Method not supported.',405);
  }else if(path==='records'){
   if(method==='GET'){const k=query.get('kind');if(k&&!/^[a-z][a-z0-9_-]{0,49}$/.test(k))throw new ApiError('Invalid research kind.');let rows;if(k)rows=await records(ctx,'research_records/'+k,{entityKey:query.get('entityKey')??undefined,limit:Number(query.get('limit')??100)});else{const r=await ctx.client.from('gridiron_records').select('*').eq('user_id',user.id).like('kind','research_records/%').order('created_at',{ascending:false}).limit(100);if(r.error)cloudError(r.error);rows=r.data??[];}result=json({records:rows.map(r=>({id:r.id,kind:r.kind.replace('research_records/',''),entityKey:r.entity_key,data:r.data?._recordFormat==='saved-research-v1'?r.data.value:r.data,source:r.source,observedAt:r.observed_at,createdAt:r.created_at,updatedAt:r.updated_at,recordOrigin:'user'}))});}
   else{const p=await inputBody(request);if(typeof p.kind!=='string'||!/^[a-z][a-z0-9_-]{0,49}$/.test(p.kind))throw new ApiError('Invalid research kind.');const value=await saveRecord(ctx,'research_records/'+p.kind,{_recordFormat:'saved-research-v1',value:finiteJson(p.data,200000)},{entityKey:p.entityKey,source:p.source,observedAt:p.observedAt});result=json({record:{...value,kind:p.kind,entityKey:p.entityKey??'',data:p.data,source:p.source??'user',observedAt:p.observedAt??new Date().toISOString()}},201);}
  }else if(pathParts[0]==='records'&&pathParts.length===2){const row=await record(ctx,pathParts[1]);if(!row.kind.startsWith('research_records/'))throw new ApiError('Saved research record not found.',404);if(method==='DELETE'){guardMutation(request);await deleteRecord(ctx,row.id);result=json({deleted:true});}else result=json({record:{id:row.id,kind:row.kind.replace('research_records/',''),entityKey:row.entity_key,data:row.data?._recordFormat==='saved-research-v1'?row.data.value:row.data,source:row.source,observedAt:row.observed_at,createdAt:row.created_at,updatedAt:row.updated_at}});
  }else if(path==='markets')result=await markets(ctx,request);
  else if(path==='model'){const p=await inputBody(request);if(p.action==='parlay')result=json(parlay(z.object({probabilities:z.array(z.number()),odds:z.array(z.number()),independenceAssumed:z.boolean().optional(),jointSamples:z.array(z.array(z.boolean())).optional()}).parse(p)));else if(p.action==='distribution'){if(typeof p.provenance!=='string'||p.provenance.length<3)throw new ApiError('Source provenance required.');result=json(distribution(p.samples,p.threshold,p.direction,p.odds));}else throw new ApiError('Choose distribution or parlay.');}
  else if(path==='contracts'){
   if(method==='GET')result=json(await cloudContracts(ctx));else{const p=await inputBody(request);if(p.action==='quote')result=json({quote:await cloudSaveQuote(ctx,p)},201);else if(p.action==='predict')result=json({prediction:await cloudSavePrediction(ctx,p)},201);else if(p.action==='settle')result=json({settlement:await cloudSettleContract(ctx,p)},201);else if(p.action==='paper')result=json({position:await cloudPaper(ctx,p)},201);else throw new ApiError('Choose quote, predict, settle or paper.');}
  }else if(path==='contracts/import'){const imported=await cloudImportContracts(ctx,await inputBody(request));result=json(imported,imported.duplicate?200:201);
  }else if(path==='injuries'){
   if(method==='GET')result=json(await cloudInjuries(ctx));else{const value=await cloudSaveInjury(ctx,await inputBody(request));if(value.resimulationRequired){try{after(()=>cloudProcessJobs(ctx!,3).then(()=>{}));}catch{/* Durable jobs can be resumed by their owner. */}}result=json(value,201);}
  }else if(path==='simulations')result=method==='GET'?json(await cloudSimulationHistory(ctx,query.get('id'))):json(await cloudRunSimulation(ctx,await inputBody(request,20*1024*1024)));
  else if(path==='quant'){
   const {handleQuant}=await import('../quant'),{attestCloudResult}=await import('./attestation');
   result=await handleQuant(request,user.id,{save:async job=>{const value=job.status==='completed'?{...job,resultProof:attestCloudResult(ctx!,job.id,job.result)}:job;let existing=false;try{await record(ctx!,job.id,'quant_runs');existing=true;}catch(e){if(!(e instanceof ApiError&&e.status===404))throw e;}if(existing)await updateRecord(ctx!,job.id,value);else await saveRecord(ctx!,'quant_runs',value,{id:job.id});},list:async()=>unwrap(await records(ctx!,'quant_runs',{limit:100})).map(job=>verifiedCloudJob(ctx!,job)),get:async id=>{try{return verifiedCloudJob(ctx!,(await record(ctx!,id,'quant_runs')).data);}catch(e){if(e instanceof ApiError&&e.status===404)return null;throw e;}}});
  }
  else if(path==='simulations/parlay'){
   const p=z.object({simulationId:z.string().uuid(),contractIds:z.array(z.string()).min(2).max(12),offer:z.object({odds:z.number().finite(),source:z.string().min(3),quotedAt:z.string().datetime({offset:true}),sportsbook:z.string(),verified:z.literal(true)}).optional()}).parse(await inputBody(request));if(p.offer&&Date.parse(p.offer.quotedAt)>Date.now()+60000)throw new ApiError('Offer timestamp cannot be in the future.');const j=(await record(ctx,p.simulationId,'simulation_jobs')).data;if(j.status!=='completed'||!j.result)throw new ApiError('A completed simulation with aligned joint outcomes is required.');verifyCloudResult(ctx,p.simulationId,j);result=json({...simulationParlay(j.result,p.contractIds,p.offer),simulationId:p.simulationId,modelVersion:j.result.modelVersion,createdAt:new Date().toISOString()});
  }else if(path==='jobs'){
   if(method==='GET')result=json(await cloudJobHistory(ctx));else{const p=await inputBody(request);if(p.action==='retry'){const j=await record(ctx,p.jobId,'simulation_jobs');if(j.data.kind!=='injury_resimulation'||j.data.status!=='blocked')throw new ApiError('An owned blocked injury job is required.');await updateRecord(ctx,j.id,{...j.data,status:'queued',error:null,updatedAt:new Date().toISOString()});}result=json(await cloudProcessJobs(ctx,1));}
  }else if(path==='history')result=json({...await cloudContracts(ctx),injuryHistory:(await cloudInjuries(ctx)).history,notifications:unwrap(await records(ctx,'notification_history',{limit:200}))});
  else if(path==='research')result=json({games:[],injuries:(await cloudInjuries(ctx)).records,injurySource:'manual_user_verified',weather:[],players:[],status:'partial',message:'No live score, usage or weather source is connected. Supplied injury citations are not independently fetched reports.',checkedAt:new Date().toISOString()});
  else if(path==='ledger/import'){const {financialImportPlan}=await import('../imports');const plan=financialImportPlan(await inputBody(request));if(plan.rows.length>500)throw new ApiError('Supabase imports support at most 500 reviewed rows per atomic batch.');const imported=await rpc(ctx,'gridiron_import_transactions',{rows:plan.rows,importId:plan.digest});result=json({...imported,digest:plan.digest,sourceHash:plan.sourceHash,duplicate:imported.imported===0},imported.imported===0?200:201);}
  else if(path==='ledger/reconcile')result=json(await rpc(ctx,'gridiron_reconcile',await inputBody(request)));
  else if(path==='ledger/backup'){const p=await inputBody(request);result=json(await exportCloud(ctx,p.password));result.headers.set('Content-Disposition','attachment; filename="gridiron-cloud-backup.encrypted.json"');}
  else if(path==='ledger/export'){const ledger=await rpc(ctx,'gridiron_ledger'),keys=['id','type','sportsbook','amount','date','note','reference'],text=[keys.join(','),...ledger.transactions.map((r:any)=>keys.map(k=>csvValue(r[k])).join(','))].join('\r\n');result=new Response(text,{headers:{'Content-Type':'text/csv; charset=utf-8','Content-Disposition':'attachment; filename="gridiron-ledger.csv"'}});}
  else if(path==='migrate'){const p=await inputBody(request,100*1024*1024);const decrypted=await decryptBackup(p.envelope,p.password),hash=createHash('sha256').update(JSON.stringify(decrypted)).digest('hex'),r=await ctx.client.rpc('gridiron_import_backup',{payload:decrypted,import_hash:hash});if(r.error)cloudError(r.error);result=json({migration:r.data,sourcePreserved:true});}
  else if(path==='devices'){
   if(method==='GET'){const values=await records(ctx,'device_registration',{limit:100});result=json({registered:values.length>0,count:values.length,encryptionConfigured:Boolean(process.env.DEVICE_TOKEN_ENCRYPTION_KEY),deliveryConfigured:false,message:'Native device registration is separate from APNs delivery. No Apple signing or APNs provider credential is configured.'});}
   else if(method==='DELETE'){guardMutation(request);const values=await records(ctx,'device_registration',{limit:100});for(const value of values)await deleteRecord(ctx,value.id);result=json({deleted:values.length});}
   else{const {validateDeviceToken,encryptDeviceToken}=await import('../native/device-tokens.server');const p=validateDeviceToken(await inputBody(request)),envelope=encryptDeviceToken(p.token),old=(await records(ctx,'device_registration',{entityKey:envelope.fingerprint,limit:1}))[0],value={platform:p.platform,environment:p.environment,envelope,registeredAt:new Date().toISOString()};if(old)await updateRecord(ctx,old.id,value);else await saveRecord(ctx,'device_registration',value,{entityKey:envelope.fingerprint});result=json({registered:true,deliveryConfigured:false},201);}
  }
  else if(path==='database/health'||path==='status')result=json({backend:'supabase',status:'connected',authenticated:true,checkedAt:new Date().toISOString(),durability:'Remote PostgreSQL; local cache is not the primary database.',profileVerified:true});
  else if(path==='warehouse'){const {handleWarehouse,cloudWarehouseStorage}=await import('../warehouse');result=await handleWarehouse(request,user.id,cloudWarehouseStorage(ctx));}
  else if(path==='pipeline'){const {handlePipeline}=await import('../pipeline');result=await handlePipeline(forwardCloudRequest(ctx),user.id,{preferences:()=>preferences(ctx!),setPreference:(key,value)=>updatePreferences(ctx!,{[key]:value}).then(()=>{}),history:async limit=>unwrap(await records(ctx!,'pipeline_run',{limit})),saveRun:async run=>{let exists=false;try{await record(ctx!,run.id,'pipeline_run');exists=true;}catch(e){if(!(e instanceof ApiError&&e.status===404))throw e;}if(exists)await updateRecord(ctx!,run.id,run);else await saveRecord(ctx!,'pipeline_run',run,{id:run.id});}});}
  else if(path==='assistant'){const {cloudAssistant}=await import('./assistant');result=await cloudAssistant(ctx,await inputBody(request));}
  else if(path==='reports'){const {buildFinancialReport}=await import('../reports');result=json(buildFinancialReport(await rpc(ctx,'gridiron_ledger'),{timezone:(await cloudSettings(ctx)).timezone,...Object.fromEntries(query)}));}
  else if(path==='audit'){const {auditWorkspace}=await import('../auditor');const h=await cloudContracts(ctx),i=await cloudInjuries(ctx),s=unwrap(await records(ctx,'simulation_jobs',{limit:100}));result=json(auditWorkspace({contracts:h.contracts,predictions:h.predictions,injuries:i.records,simulations:s}));}
  else throw new ApiError('This cloud operation is not implemented. The application did not fall back to a local database.',501);
  return finishCloud(ctx,result);
 }catch(error){if(!ctx&&error instanceof CloudAuthUnavailable)ctx=error.context;const response=error instanceof z.ZodError?json({error:error.issues.map(i=>i.path.join('.')+': '+i.message).join('; ')},400):error instanceof ProviderError?json({error:error.message},error.status):errorResponse(error);return finishCloud(ctx,response);}
}
