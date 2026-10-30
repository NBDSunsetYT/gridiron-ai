import type {ChatCompletionTool} from 'openai/resources/chat/completions';
import {z} from 'zod';
import {requestOrigin} from './auth';
const domains=['quarterbacks','receivers','running_backs','tight_ends','defensive_coverage','offensive_line','defensive_line','injuries','weather','simulation','market_pricing','model_validation'] as const;
const definitions=[
 ['run_saved_simulation','Run complete games using a fitted model already owned by this user. The statistical service calculates outputs; never invent a fit ID or model. Requires an explicit simulation request.',{fitJobId:{type:'string'},home:{type:'string'},away:{type:'string'},eventStart:{type:'string'},simulations:{type:'integer',enum:[10000,50000,100000]},seed:{type:'integer'}} ,['fitJobId','home','away','eventStart','simulations']],
 ['get_specialist_evidence','Retrieve structured evidence for one NFL research specialty. Missing records return unavailable; this is evidence selection, not a separate predictive model.',{specialist:{type:'string',enum:domains}},['specialist']],
 ['read_research_memory','Read user-approved preferences and saved research reports from the authenticated database.',{},[]],
 ['save_research_report','Save a timestamped research report composed of actual contract, injury, simulation and auditor records. Use when the user asks to save/export research.',{title:{type:'string'}},['title']],
 ['remember_research_preference','Persist a research preference only when the current user explicitly asks you to remember/save a preference. This never changes roles, authentication or financial settings.',{key:{type:'string'},value:{type:'string'}},['key','value']]
] as const;
export const additionalResearchTools:ChatCompletionTool[]=definitions.map(([name,description,properties,required])=>({type:'function',function:{name,description,parameters:{type:'object',properties,required:[...required],additionalProperties:false}}}));
export const isResearchTool=(name:string)=>definitions.some(d=>d[0]===name);
/** All requests reuse the caller's server cookies, so the selected backend enforces ownership again. */
export async function executeResearchTool(request:Request,name:string,args:unknown,prompt:string){
 const call=async(path:string,body?:unknown)=>{
  const origin=requestOrigin(request),headers:Record<string,string>={cookie:request.headers.get('cookie')||'',origin};
  if(body)headers['Content-Type']='application/json';
  const response=await fetch(new URL(path,origin),{method:body?'POST':'GET',headers,body:body?JSON.stringify(body):undefined,cache:'no-store',signal:AbortSignal.timeout(path.includes('simulations')?245000:20000)});
  const data=await response.json();if(!response.ok)throw Error(data.error||`Evidence request failed (${response.status}).`);return data;
 };
 const timestamp=new Date().toISOString();
 if(name==='run_saved_simulation'){
  if(!/\b(simulat\w*|run\b.*\bgame|rerun|re-run)\b/i.test(prompt))throw Error('A current explicit simulation request is required.');
  const p=z.object({fitJobId:z.string().uuid(),home:z.string().min(2).max(80),away:z.string().min(2).max(80),eventStart:z.string().datetime({offset:true}),simulations:z.union([z.literal(10000),z.literal(50000),z.literal(100000)]),seed:z.number().int().min(0).max(2147483647).default(2026)}).parse(args);
  const saved=await call('/api/simulations?id='+encodeURIComponent(p.fitJobId));
  if(saved.job?.kind!=='fit'||saved.job?.status!=='completed'||!saved.job?.result?.model)throw Error('An owned completed fit with its signed model is required.');
  const {fitJobId,...input}=p;const result=await call('/api/simulations',{action:'simulate',...input,model:saved.job.result.model});
  return{source:'Authenticated saved-model statistical service',checkedAt:timestamp,id:result.id,modelVersion:result.modelVersion,evidenceCutoff:result.evidenceCutoff,simulations:result.simulations,home:result.home,away:result.away,homeWinProbability:result.homeWinProbability,awayWinProbability:result.awayWinProbability,tieProbability:result.tieProbability,scoreDistributions:result.scoreDistributions,contracts:result.contracts,uncertainty:result.uncertainty,limitations:result.limitations};
 }
 if(name==='get_specialist_evidence'){
  const {specialist}=z.object({specialist:z.enum(domains)}).parse(args);
  const paths:Record<string,string>={injuries:'/api/injuries',simulation:'/api/simulations',market_pricing:'/api/contracts',model_validation:'/api/audit',quarterbacks:'/api/records?kind=quarterback_statistics',receivers:'/api/records?kind=receiver_usage',running_backs:'/api/records?kind=rushing_usage',tight_ends:'/api/records?kind=tight_end_usage',defensive_coverage:'/api/records?kind=defensive_matchups',offensive_line:'/api/records?kind=offensive_line',defensive_line:'/api/records?kind=defensive_line',weather:'/api/records?kind=weather'};
  const evidence=await call(paths[specialist]);
  return{specialist,checkedAt:timestamp,evidence,status:Array.isArray(evidence.records)&&evidence.records.length===0?'unavailable':'inspect_source_records',method:'Deterministic evidence retrieval; no invented specialist estimates or claim of independent live research.'};
 }
 if(name==='read_research_memory')return{checkedAt:timestamp,preferences:await call('/api/preferences'),reports:await call('/api/records?kind=saved_report')};
 if(name==='save_research_report'){
  if(!/\b(save|export|report)\b/i.test(prompt))throw Error('The user must explicitly request a saved report.');
  const {title}=z.object({title:z.string().min(3).max(160)}).parse(args);
  const paths=['/api/contracts','/api/injuries','/api/simulations','/api/audit'];
  const results=await Promise.allSettled(paths.map(path=>call(path)));
  const sections=results.map((result,index)=>({path:paths[index],checkedAt:timestamp,status:result.status==='fulfilled'?'available':'unavailable',evidence:result.status==='fulfilled'?result.value:undefined,reason:result.status==='rejected'?'Source request could not be verified':undefined}));
  return call('/api/records',{kind:'saved_report',entityKey:title,data:{title,createdAt:timestamp,sections,method:'Immutable-at-capture source snapshot; AI conclusions are not a statistical result.'},source:'GRIDIRON authenticated research tools',observedAt:timestamp});
 }
 if(name==='remember_research_preference'){
  if(!/\bremember\b|\bsave\b.*\bpreference\b/i.test(prompt))throw Error('Explicit user approval to remember this preference is required.');
  const p=z.object({key:z.string().regex(/^[a-z0-9_]{1,60}$/),value:z.string().min(1).max(2000)}).parse(args);
  const response=await fetch(new URL('/api/preferences',requestOrigin(request)),{method:'PATCH',headers:{'content-type':'application/json',cookie:request.headers.get('cookie')||'',origin:requestOrigin(request)},body:JSON.stringify({preferences:{['research_'+p.key]:{value:p.value,approvedAt:timestamp,approvalPrompt:prompt.slice(0,4000)}}}),cache:'no-store'});
  const data=await response.json();if(!response.ok)throw Error(data.error||'Preference could not be saved.');return{saved:true,key:'research_'+p.key,approvedAt:timestamp};
 }
 throw Error('Unknown research tool.');
}
