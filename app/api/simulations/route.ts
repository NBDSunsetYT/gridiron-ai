import {assertComputeAllowed} from '@/lib/compute/policy';
import {createHash,randomUUID} from 'node:crypto';
import {NextResponse} from 'next/server';
import {ApiError,errorResponse,rateLimit,requireUser,requestOrigin} from '@/lib/auth';
import {getDb} from '@/lib/db';
import {simulationPayload} from '@/lib/simulation-input';
export const runtime='nodejs';
export const maxDuration=300;
const MAX_BODY=20*1024*1024;
async function readInput(request:Request){
 const origin=request.headers.get('origin');const expected=requestOrigin(request);
 if(origin&&origin!==expected)throw new ApiError('Cross-origin requests are not allowed.',403);
 if(!(request.headers.get('content-type')||'').includes('application/json'))throw new ApiError('Use application/json.',415);
 if(Number(request.headers.get('content-length')||0)>MAX_BODY)throw new ApiError('Simulation input exceeds 20 MB.',413);
 if(!request.body)throw new ApiError('A simulation request body is required.');
 const reader=request.body.getReader(),decoder=new TextDecoder();let bytes=0,text='';
 for(;;){const {value,done}=await reader.read();if(done)break;bytes+=value.byteLength;if(bytes>MAX_BODY){await reader.cancel();throw new ApiError('Simulation input exceeds 20 MB.',413);}text+=decoder.decode(value,{stream:true});}text+=decoder.decode();
 const input=JSON.parse(text);if(!input||!['fit','simulate'].includes(input.action))throw new ApiError('Choose fit or simulate.');return {input,hash:createHash('sha256').update(text).digest('hex'),bytes};
}
function decode(row:any,detail=false){const data=JSON.parse(row.data);const result=row.result?JSON.parse(row.result):null;return {id:row.id,kind:row.kind,status:row.status,data,result:detail?result:result?{summary:result.summary,modelVersion:result.modelVersion,provenance:result.provenance}:null,error:row.error,createdAt:row.created_at,updatedAt:row.updated_at};}
export async function GET(request:Request){try{const user=await requireUser(request);const id=new URL(request.url).searchParams.get('id');const db=getDb();const configured=Boolean(process.env.SIMULATION_SERVICE_URL&&process.env.SIMULATION_SERVICE_TOKEN);if(id){const row=db.prepare('SELECT * FROM simulation_jobs WHERE id=? AND user_id=?').get(id,user.id);if(!row)throw new ApiError('Simulation record not found.',404);return NextResponse.json({job:decode(row,true),service:{configured}},{headers:{'Cache-Control':'private, no-store'}});}const rows=db.prepare('SELECT * FROM simulation_jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 60').all(user.id);return NextResponse.json({jobs:rows.map(row=>decode(row)),service:{configured,message:configured?'Quantitative service configured; availability is verified when a request runs.':'SIMULATION_SERVICE_URL and SIMULATION_SERVICE_TOKEN are not configured.'}},{headers:{'Cache-Control':'private, no-store'}});}catch(e){return errorResponse(e);}}
export async function POST(request:Request){let jobId:string|undefined;let userId:string|undefined;try{
 const user=await requireUser(request);userId=user.id;assertComputeAllowed();const {input,hash,bytes}=await readInput(request);
 if(input.action==='simulate'&&input.modelJobId){
  if(typeof input.modelJobId!=='string'||!input.modelJobId.match(/^[a-f0-9-]{36}$/i))throw new ApiError('A valid owned fitted-model job ID is required.');
  const fitted=getDb().prepare('SELECT result FROM simulation_jobs WHERE id=? AND user_id=? AND kind=? AND status=?').get(input.modelJobId,user.id,'fit','completed') as {result:string|null}|undefined;
  if(!fitted?.result)throw new ApiError('Owned completed fitted model not found.',404);
  const artifact=JSON.parse(fitted.result)?.model;if(!artifact)throw new ApiError('The saved fitted model is unavailable.');
  input.model=artifact;delete input.modelJobId;
 }
 rateLimit(`simulations:${user.id}`,12,60*60*1000);
 const endpoint=process.env.SIMULATION_SERVICE_URL,token=process.env.SIMULATION_SERVICE_TOKEN;if(!endpoint||!token)throw new ApiError('The quantitative service is unavailable. Configure SIMULATION_SERVICE_URL and SIMULATION_SERVICE_TOKEN on the server. No outcomes have been simulated.',503);
 const base=new URL(endpoint);if(!['http:','https:'].includes(base.protocol))throw new ApiError('Simulation service configuration is invalid.',503);
 const action=input.action,payload=simulationPayload(input);jobId=randomUUID();const now=new Date().toISOString();const audit={inputHash:hash,inputBytes:bytes,source:input.source??input.model?.source??input.model?.provenance?.source??null,asOf:input.asOf??input.model?.asOf??null,home:input.home??null,away:input.away??null,eventStart:input.eventStart??null,simulations:input.simulations??null,seed:input.seed??null,modelVersion:input.model?.modelVersion??input.model?.version??null,scenario:input.scenario??null,contracts:input.contracts??null,injuryEntityKeys:input.injuryEntityKeys??[]};
 getDb().transaction(()=>{getDb().prepare('INSERT INTO simulation_jobs(id,user_id,kind,status,data,result,error,created_at,updated_at) VALUES(?,?,?,?,?,NULL,NULL,?,?)').run(jobId,user.id,action,'running',JSON.stringify(audit),now,now);if(action==='simulate')getDb().prepare('INSERT INTO simulation_inputs(id,user_id,job_id,data,created_at) VALUES(?,?,?,?,?)').run(randomUUID(),user.id,jobId,JSON.stringify(input),now);})();
 let response:Response;try{response=await fetch(new URL(action==='fit'?'fit':'simulate',base.href.endsWith('/')?base:new URL(base.href+'/')),{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${token}`},body:JSON.stringify(payload),signal:AbortSignal.timeout(240000),cache:'no-store'});}catch{throw new ApiError('The quantitative service could not complete this request. It may be unavailable or the runtime limit was reached. Your previous results remain available.',502);}
 let result:any;try{result=await response.json();}catch{throw new ApiError('The quantitative service returned an invalid response.',502);}
 if(!result||typeof result!=='object'||Array.isArray(result))throw new ApiError('The quantitative service returned an invalid result object.',502);if(!response.ok){const details=typeof result.detail==='string'?result.detail:typeof result.error==='string'?result.error:'The quantitative service rejected the input. Verify required evidence and configuration.';throw new ApiError(details.slice(0,1200),response.status>=400&&response.status<500?response.status:502);}
 getDb().prepare('UPDATE simulation_jobs SET status=?,result=?,updated_at=? WHERE id=? AND user_id=?').run('completed',JSON.stringify(result),new Date().toISOString(),jobId,user.id);
 return NextResponse.json({id:jobId,status:'completed',...result});
 }catch(e){if(jobId&&userId)getDb().prepare('UPDATE simulation_jobs SET status=?,error=?,updated_at=? WHERE id=? AND user_id=?').run('failed',e instanceof ApiError?e.message:'The simulation request failed.',new Date().toISOString(),jobId,userId);return errorResponse(e);}}
