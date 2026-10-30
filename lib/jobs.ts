import {randomUUID,createHash} from 'node:crypto';
import {getDb} from './db';
import {savePrediction} from './contracts';
import {simulationPayload} from './simulation-input';
type Row=Record<string,any>;
const iso=()=>new Date().toISOString();
class JobRunError extends Error{constructor(message:string,public retryable=false){super(message);}}
function notice(userId:string,data:Row){const now=iso(),id=randomUUID();getDb().prepare('INSERT INTO notification_history(id,user_id,data,created_at) VALUES(?,?,?,?)').run(id,userId,JSON.stringify({id,...data,delivery:'in_app_only',createdAt:now}),now);}
export function injuryScenarios(record:Row):{status:string;weight:number}[]|null {
  if(['out','injured_reserve','suspended'].includes(record.status))return[{status:'inactive',weight:1}];
  const c=record.cohorts,total=c?c.active+c.limited+c.out:0;
  if(!c||total<20)return null;
  return[{status:'active',weight:c.active/total},{status:'limited',weight:c.limited/total},{status:'inactive',weight:c.out/total}].filter(s=>s.weight>0);
}
export function queueInjuryResimulation(userId:string,prediction:Row,record:Row){
  const now=iso(),id=randomUUID(),scenarios=injuryScenarios(record);let reason:string|null=null;
  const sourceId=prediction.evidence?.simulationId;
  const original=sourceId?getDb().prepare('SELECT data FROM simulation_inputs WHERE user_id=? AND job_id=?').get(userId,sourceId) as {data:string}|undefined:undefined;
  if(!original)reason='Complete original signed simulation input is unavailable; supply evidence and run a simulation before automatic replay.';
  else if(!scenarios)reason='Uncertain availability has no documented cohort of at least 20 comparable outcomes; numerical scenario weights are unavailable.';
  else if(Date.now()-Date.parse(record.publicationAt)>72*3600000||Date.now()-Date.parse(record.checkedAt)>24*3600000)reason='Injury evidence is stale under the 72-hour publication /24-hour check policy; obtain a current verified source before automatic replay.';
  else if(Date.parse(prediction.eventStart)<=Date.now())reason='Event has already started; no pre-event resimulation will be created.';
  else if(!process.env.SIMULATION_SERVICE_URL||!process.env.SIMULATION_SERVICE_TOKEN)reason='The private simulation service is not configured.';
  const input=original?JSON.parse(original.data):null;
  const existingPlayer=input?.scenario?.playerId??input?.injuryMixture?.playerId;
  if(existingPlayer&&existingPlayer!==record.entityKey)reason='Joint multiple-player injury scenario evidence is not modeled; automatic replay is blocked.';
  const data={id,predictionId:prediction.id,sourceJobId:sourceId??null,injuryRecordId:record.id,entityKey:record.entityKey,scenarios,reason,requestedAt:now};
  getDb().prepare('INSERT INTO simulation_jobs(id,user_id,kind,status,data,error,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)').run(id,userId,'injury_resimulation',reason?'blocked':'queued',JSON.stringify(data),reason,now,now);
  return{id,status:reason?'blocked':'queued',reason};
}
const MIXTURE_TOLERANCE=1e-8;
const isProbability=(p:unknown):p is number=>typeof p==='number'&&Number.isFinite(p)&&p>=0&&p<=1;
const stable=(value:any):string=>{if(Array.isArray(value))return '['+value.map(v=>stable(v)).join(',')+']';if(value&&typeof value==='object')return '{'+Object.keys(value).filter(k=>value[k]!==undefined).sort().map(k=>JSON.stringify(k)+':'+stable(value[k])).join(',')+'}';return JSON.stringify(value)??'null';};
function checkHistogram(distribution:Row|undefined,samples:number,label:string){
  if(!distribution||!Array.isArray(distribution.histogram)||!distribution.histogram.length||distribution.histogram.some((r:Row)=>!Number.isFinite(r.value)||!Number.isFinite(r.count)||r.count<0))throw new Error(`Complete finite histogram required for ${label}.`);
  const count=distribution.histogram.reduce((sum:number,r:Row)=>sum+r.count,0);
  if(Math.abs(count-samples)>Math.max(1e-6,samples*MIXTURE_TOLERANCE))throw new Error(`Histogram counts do not reconcile with completed games for ${label}.`);
}
function combineHistogram(distributions:Row[],weights:number[],total:number){
  const counts=new Map<number,number>();
  distributions.forEach((d,i)=>{const denominator=d.histogram.reduce((s:number,r:Row)=>s+r.count,0);for(const row of d.histogram)counts.set(row.value,(counts.get(row.value)??0)+row.count/denominator*weights[i]*total);});
  const histogram=Array.from(counts,([value,count])=>({value,count})).filter(r=>r.count>0).sort((a,b)=>a.value-b.value);
  const quantile=(p:number)=>{let sum=0;for(const r of histogram){sum+=r.count;if(sum>=total*p)return r.value;}return histogram.at(-1)?.value??null;};
  return{mean:histogram.reduce((s,r)=>s+r.value*r.count,0)/total,median:quantile(.5),interval90:[quantile(.05),quantile(.95)],histogram,countMeaning:'Scenario-weighted research counts, not an independent binomial sample.'};
}
/** Combine complete games under fixed documented scenario weights. No input is mutated. */
export function combineScenarios(results:Row[],weights:number[]):Row {
  if(!Array.isArray(results)||!results.length||!Array.isArray(weights)||results.length!==weights.length||weights.some(w=>!Number.isFinite(w)||w<0||w>1))throw new Error('Complete scenario results and finite nonnegative normalized evidence-based weights required.');
  const sum=weights.reduce((a,b)=>a+b,0);
  if(!Number.isFinite(sum)||Math.abs(sum-1)>1e-9)throw new Error('Complete scenario results and normalized evidence-based weights required.');
  // Remove only rounding error in an already normalized supplied cohort distribution.
  const normalized=weights.map(w=>w/sum),first=results[0];
  if(!first||typeof first!=='object')throw new Error('Complete scenario result objects are required.');
  const contractIds=(first.contracts??[]).map((c:Row)=>c.id);
  if(!Array.isArray(first.contracts)||contractIds.some((id:any)=>typeof id!=='string'||!id)||new Set(contractIds).size!==contractIds.length)throw new Error('Distinct scenario contract identifiers are required.');
  const positions:Map<string,number>[]=[];
  for(const result of results){
    if(!result||!Number.isSafeInteger(result.simulations)||result.simulations<=0)throw new Error('Every scenario must record a positive integer count of completed games.');
    if(result.injuryMixture||result.uncertainty?.method==='stratified_scenario_mixture')throw new Error('Nested weighted aggregates are not independent completed-game strata; supply original scenario runs.');
    for(const key of ['modelVersion','eventStart','inputDataVersion','home','away'])if(typeof first[key]!=='string'||!first[key]||result[key]!==first[key])throw new Error('Scenario provenance, participants and event must match.');
    if(result.evidenceCutoff!==first.evidenceCutoff)throw new Error('Scenario evidence cutoffs must match.');
    if(!['homeWinProbability','awayWinProbability','tieProbability'].every(key=>isProbability(result[key]))||Math.abs(result.homeWinProbability+result.awayWinProbability+result.tieProbability-1)>MIXTURE_TOLERANCE)throw new Error('Scenario win/tie probabilities must be finite and sum to one.');
    if(!Array.isArray(result.contracts)||result.contracts.length!==contractIds.length)throw new Error('Scenario contract sets must match.');
    const index=new Map<string,number>();result.contracts.forEach((c:Row,i:number)=>index.set(c.id,i));positions.push(index);
    if(index.size!==contractIds.length||contractIds.some((id:string)=>!index.has(id)))throw new Error('Scenario contract sets must match.');
    for(const contract of result.contracts){
      const reference=first.contracts.find((c:Row)=>c.id===contract.id);
      if(!contract.settlement||stable(contract.settlement)!==stable(reference.settlement))throw new Error('Scenario contract settlement definitions and participants must match exactly.');
      if(!isProbability(contract.probability)||!isProbability(contract.pushProbability)||contract.probability+contract.pushProbability>1+MIXTURE_TOLERANCE)throw new Error('Scenario contract probabilities must be finite and coherent.');
    }
    if(!result.scoreDistributions||Object.keys(result.scoreDistributions).sort().join('|')!==[first.home,first.away].sort().join('|'))throw new Error('Scenario score distributions must identify the same two teams.');
    for(const team of [first.home,first.away])checkHistogram(result.scoreDistributions[team],result.simulations,`${team} score`);
    checkHistogram(result.totalDistribution,result.simulations,'total points');checkHistogram(result.marginDistribution,result.simulations,'score margin');
    if(!result.players||typeof result.players!=='object'||Array.isArray(result.players))throw new Error('Scenario player distributions are required.');
    for(const [player,stats] of Object.entries(result.players)){
      if(!stats||typeof stats!=='object'||Array.isArray(stats))throw new Error('Player statistics must be identified distributions.');
      for(const [stat,distribution] of Object.entries(stats))checkHistogram(distribution as Row,result.simulations,`${player} ${stat}`);
    }
    const joint=result.jointOutcomes;
    if(!Array.isArray(joint)||joint.some((r:Row)=>!Array.isArray(r.outcomes)||r.outcomes.length!==contractIds.length||r.outcomes.some((v:any)=>!['yes','no','push'].includes(v))||!Number.isFinite(r.count)||r.count<0))throw new Error('Scenario joint outcomes are invalid.');
    if(contractIds.length){
      if(Math.abs(joint.reduce((n:number,r:Row)=>n+r.count,0)-result.simulations)>Math.max(1e-6,result.simulations*MIXTURE_TOLERANCE))throw new Error('Scenario joint outcomes must reconcile with completed games.');
      result.contracts.forEach((c:Row,i:number)=>{for(const [state,probability] of [['yes',c.probability],['push',c.pushProbability]] as const){const observed=joint.filter((r:Row)=>r.outcomes[i]===state).reduce((n:number,r:Row)=>n+r.count,0)/result.simulations;if(Math.abs(observed-probability)>MIXTURE_TOLERANCE)throw new Error('Scenario probabilities must agree with shared-game joint outcomes.');}});
    }
  }
  if(results.length===1)return{...structuredClone(first),injuryMixture:{weights:[1],method:'single confirmed availability scenario',scenarioSimulations:[first.simulations],scenarioSeeds:[first.seed??null]}};
  const total=results.reduce((s,r)=>s+r.simulations,0),weighted=(key:string)=>results.reduce((s,r,i)=>s+r[key]*normalized[i],0);
  if(!Number.isSafeInteger(total))throw new Error('Total completed game count exceeds the supported exact range.');
  const seeds=results.map(r=>r.seed),positive=normalized.map((w,i)=>({w,i})).filter(r=>r.w>0);
  const distinctStreams=positive.every(({i})=>Number.isSafeInteger(seeds[i])&&!results[i].injuryMixture)&&new Set(positive.map(({i})=>seeds[i])).size===positive.length;
  const varianceFactor=normalized.reduce((s,w,i)=>s+w*w/results[i].simulations,0);
  // A finite-sample bound avoids zero-width numerical confidence at 0/1. Missing or reused
  // seeds use a simultaneous per-stratum bound, valid without cross-stratum independence.
  const radius=distinctStreams?Math.sqrt(Math.log(40)*varianceFactor/2):positive.reduce((s,{w,i})=>s+w*Math.sqrt(Math.log(40*positive.length)/(2*results[i].simulations)),0);
  const interval=(p:number)=>[Math.max(0,p-radius),Math.min(1,p+radius)];
  const se=(probabilities:number[])=>distinctStreams?Math.sqrt(probabilities.reduce((s,p,i)=>s+normalized[i]**2*p*(1-p)/results[i].simulations,0)):null;
  const seUpper=(_probabilities:number[])=>distinctStreams?Math.sqrt(varianceFactor/4):normalized.reduce((s,w,i)=>s+w/(2*Math.sqrt(results[i].simulations)),0);
  const method=distinctStreams?'Stratified Monte Carlo under fixed weights and distinct seeded pseudorandom streams; finite-sample weighted Hoeffding interval.':'Fixed-weight scenario mixture; cross-scenario independence is unverified. Simultaneous per-stratum Hoeffding bound; independent-strata SE withheld.';
  const contracts=first.contracts.map((c:Row)=>{
    const aligned=results.map((r,i)=>r.contracts[positions[i].get(c.id)!]);
    const probabilities=aligned.map(r=>r.probability),probability=probabilities.reduce((s,p,i)=>s+p*normalized[i],0),pushProbability=aligned.reduce((s:number,r:Row,i:number)=>s+r.pushProbability*normalized[i],0);
    return{...structuredClone(c),probability,pushProbability,conditionalNonPushProbability:pushProbability<1?probability/(1-pushProbability):null,monteCarloSE:se(probabilities),monteCarloSEUpperBound:seUpper(probabilities),monteCarloInterval95:interval(probability),uncertaintyMethod:method};
  });
  const joint=new Map<string,number>();results.forEach((r,i)=>{for(const row of r.jointOutcomes){const aligned=contractIds.map((id:string)=>row.outcomes[positions[i].get(id)!]),key=JSON.stringify(aligned);joint.set(key,(joint.get(key)??0)+row.count/r.simulations*normalized[i]*total);}});
  const players:Row={},absentPlayers:string[]=[];
  const names=new Set(results.flatMap(r=>Object.keys(r.players)));
  for(const player of names){
    players[player]={};const stats=new Set(results.flatMap(r=>Object.keys(r.players[player]??{})));
    for(const stat of stats){
      const aligned=results.map((r,i)=>{if(!Object.hasOwn(r.players,player)){if(normalized[i]>0)absentPlayers.push(`${player}:scenario${i}`);return{histogram:[{value:0,count:r.simulations}]};}if(!Object.hasOwn(r.players[player],stat))throw new Error('A present player has a missing statistic; complete aligned distributions are required.');return r.players[player][stat];});
      players[player][stat]=combineHistogram(aligned,normalized,total);
    }
  }
  const scoreDistributions:Row={};for(const team of [first.home,first.away])scoreDistributions[team]=combineHistogram(results.map(r=>r.scoreDistributions[team]),normalized,total);
  const gameEnvironment:Row={},unavailableEnvironmentKeys:string[]=[];
  const eventCounters=new Set(['plays','drives','overtime','interceptions','sacks','punts','fieldGoalAttempts','fieldGoals','fumblesLost','touchdowns','safeties','defensiveTouchdowns']);
  for(const key of new Set(results.flatMap(r=>Object.keys(r.gameEnvironment??{})))){
    const values=results.map(r=>r.gameEnvironment?.[key]??(eventCounters.has(key)?0:undefined));
    if(values.some(v=>!Number.isFinite(v))){unavailableEnvironmentKeys.push(key);continue;}
    gameEnvironment[key]=values.reduce((s,v,i)=>s+v*normalized[i],0);
  }
  const home=results.map(r=>r.homeWinProbability),away=results.map(r=>r.awayWinProbability),ties=results.map(r=>r.tieProbability),homeWinProbability=weighted('homeWinProbability');
  return{...structuredClone(first),scenario:null,seed:null,createdAt:iso(),evidence:{method:'Per-scenario evidence is retained separately; distinct historical coverage cannot be inferred by summing overlapping cohorts.',scenarios:results.map((r,i)=>({weight:normalized[i],evidence:r.evidence??null}))},simulations:total,homeWinProbability,awayWinProbability:weighted('awayWinProbability'),tieProbability:weighted('tieProbability'),monteCarloSE:se(home),monteCarloSEUpperBound:seUpper(home),monteCarloInterval95:interval(homeWinProbability),awayMonteCarloSE:se(away),awayMonteCarloInterval95:interval(weighted('awayWinProbability')),tieMonteCarloSE:se(ties),tieMonteCarloInterval95:interval(weighted('tieProbability')),scoreDistributions,totalDistribution:combineHistogram(results.map(r=>r.totalDistribution),normalized,total),marginDistribution:combineHistogram(results.map(r=>r.marginDistribution),normalized,total),players,gameEnvironment,contracts,jointOutcomes:Array.from(joint,([key,count])=>({outcomes:JSON.parse(key),count})),convergence:[],injuryMixture:{weights:normalized,method:'empirical cohort-weighted scenario mixture; fractional histogram counts are weighted research counts',scenarioSimulations:results.map(r=>r.simulations),scenarioSeeds:seeds.map(seed=>seed??null),distinctStreams,unavailableEnvironmentKeys,absentPlayerZeroPolicy:'Generated service results omit players with no participation; an entirely absent player is assigned zero outcomes for those completed games. A missing stat on a present player is rejected.',absentPlayers:Array.from(new Set(absentPlayers))},uncertainty:{method:'stratified_scenario_mixture',monteCarlo:method,modelInterval:null,scenarioWeightInterval:null,model:'Aggregate parameter/model and cohort-weight uncertainty are not estimated. The reported bound describes numerical sampling error conditional on the supplied fitted evidence and fixed weights.'}};
}
async function executeJob(row:Row){
  const userId=row.user_id,data=JSON.parse(row.data),db=getDb();
  const original=db.prepare('SELECT data FROM simulation_inputs WHERE user_id=? AND job_id=?').get(userId,data.sourceJobId) as {data:string}|undefined;
  const predictionRow=db.prepare('SELECT data FROM prediction_snapshots WHERE user_id=? AND id=?').get(userId,data.predictionId) as {data:string}|undefined;
  if(!original||!predictionRow)throw new Error('Complete original input or immutable prediction no longer exists.');
  const originalInput=JSON.parse(original.data),prediction=JSON.parse(predictionRow.data);
  const currentSource=db.prepare('SELECT id FROM injury_history WHERE user_id=? AND entity_key=? ORDER BY created_at DESC,rowid DESC LIMIT 1').get(userId,data.entityKey) as {id:string}|undefined;
  if(currentSource?.id!==data.injuryRecordId)throw new JobRunError('A newer injury report superseded this queued replay. Use the newer source and job.');
  if(Date.parse(originalInput.eventStart)<=Date.now())throw new Error('Event has started. No post-start forecast will be created.');
  const endpoint=process.env.SIMULATION_SERVICE_URL,token=process.env.SIMULATION_SERVICE_TOKEN;if(!endpoint||!token)throw new Error('The private simulation service is not configured.');
  const scenarios=data.scenarios as {status:string;weight:number}[];if(!scenarios?.length)throw new Error('No supported evidence-based injury scenario exists.');
  const results:Row[]=[];let completeInput:Row|undefined;
  for(const scenario of scenarios){
    const payload=simulationPayload(originalInput,{replay:true});payload.scenario={playerId:data.entityKey,status:scenario.status};
    // Separate reproducible streams avoid silently treating common-random-number runs as independent strata.
    payload.seed=Number.parseInt(createHash('sha256').update(JSON.stringify({seed:originalInput.seed??1,playerId:data.entityKey,status:scenario.status,model:originalInput.model?.sha256??null})).digest('hex').slice(0,12),16);
    completeInput={action:'simulate',...payload,injuryEntityKeys:originalInput.injuryEntityKeys??[]};
    const base=new URL(endpoint.endsWith('/')?endpoint:endpoint+'/');
    let response:Response;try{response=await fetch(new URL('simulate',base),{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${token}`},body:JSON.stringify(payload),signal:AbortSignal.timeout(240000),cache:'no-store'});}catch{throw new JobRunError('The quantitative service could not be reached. No replacement forecast was invented.',true);}
    let result:Row;try{result=await response.json();}catch{throw new JobRunError('The quantitative service returned invalid JSON.',true);}
    if(!response.ok){const detail=typeof result.detail==='string'?result.detail:'The service could not run this scenario.';throw new JobRunError(detail.slice(0,1000),response.status===429||response.status>=500);}
    results.push(result);
  }
  const result=combineScenarios(results,scenarios.map(s=>s.weight)),now=iso();
  // A single scenario has an exact replay input; a mixture retains the original input and explicit scenario recipe.
  const replay=scenarios.length===1?completeInput:{...originalInput,injuryMixture:{playerId:data.entityKey,scenarios}};
  db.transaction(()=>{
    db.prepare('INSERT INTO simulation_inputs(id,user_id,job_id,data,created_at) VALUES(?,?,?,?,?)').run(randomUUID(),userId,row.id,JSON.stringify(replay),now);
    db.prepare('UPDATE simulation_jobs SET status=?,result=?,updated_at=? WHERE id=? AND user_id=?').run('completed',JSON.stringify(result),now,row.id,userId);
  })();
  try{
    const currentInjury=db.prepare('SELECT id FROM injury_history WHERE user_id=? AND entity_key=? ORDER BY created_at DESC,rowid DESC LIMIT 1').get(userId,data.entityKey) as {id:string}|undefined;
    if(currentInjury?.id!==data.injuryRecordId)throw new Error('Injury evidence changed during execution. This run remains historical; use the newer queued replay before creating a fresh valuation.');
    const quoteRow=db.prepare('SELECT id FROM contract_quotes WHERE user_id=? AND contract_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1').get(userId,prediction.contractId) as {id:string}|undefined;
    const next=savePrediction(userId,{quoteId:quoteRow?.id??prediction.quoteId,probability:.5,side:prediction.side,quantity:prediction.quantity,asOf:now,inputsHash:createHash('sha256').update(JSON.stringify(replay)).digest('hex'),modelVersion:result.modelVersion,injuryEntityKeys:Array.from(new Set([...(prediction.injuryEntityKeys??[]),data.entityKey])),supersedesPredictionId:prediction.id,evidence:{source:`Automatic replay of signed simulation ${data.sourceJobId}; injury ${data.injuryRecordId}`,method:scenarios.length===1?'Empirical inactive/active/limited historical scenario':'Empirical cohort-weighted availability scenario mixture',sampleSize:result.simulations,simulationId:row.id}});
    notice(userId,{type:'resimulation_completed',jobId:row.id,previousPredictionId:prediction.id,predictionId:next.id,reason:'Updated probability snapshot appended from documented injury scenario evidence. Quote freshness and total model uncertainty remain explicit.'});
  }catch(error){notice(userId,{type:'resimulation_requires_review',jobId:row.id,previousPredictionId:prediction.id,reason:error instanceof Error?error.message:'Completed simulation requires manual valuation review.'});}
}
/** Durable queue; callers can rerun after restart. A 20-minute lease prevents concurrent duplicate execution. */
export async function processSimulationJobs(userId?:string,limit=1){
  const db=getDb(),cutoff=new Date(Date.now()-20*60000).toISOString(),now=iso();
  const filter=userId?' AND user_id=?':'';const args=userId?[cutoff,userId]:[cutoff];
  const rows=(db.prepare(`SELECT * FROM simulation_jobs WHERE kind='injury_resimulation' AND (status='queued' OR (status='running' AND updated_at<?))${filter} ORDER BY created_at LIMIT 100`).all(...args) as Row[]).filter(row=>{const data=JSON.parse(row.data);return !data.nextAttemptAt||Date.parse(data.nextAttemptAt)<=Date.now();}).slice(0,Math.min(3,Math.max(1,limit)));
  const results:Row[]=[];
  for(const row of rows){
    const attempted={...JSON.parse(row.data),attempts:(JSON.parse(row.data).attempts??0)+1};
    const claim=db.prepare("UPDATE simulation_jobs SET status='running',data=?,updated_at=? WHERE id=? AND (status='queued' OR (status='running' AND updated_at<?))").run(JSON.stringify(attempted),now,row.id,cutoff);if(!claim.changes)continue;
    try{await executeJob({...row,data:JSON.stringify(attempted)});results.push({id:row.id,status:'completed'});}catch(error){const message=error instanceof Error?error.message:'Resimulation failed.',retry=error instanceof JobRunError&&error.retryable&&attempted.attempts<3,status=retry?'queued':'blocked',nextAttemptAt=retry?new Date(Date.now()+30000*2**attempted.attempts).toISOString():null;
      db.prepare('UPDATE simulation_jobs SET status=?,data=?,error=?,updated_at=? WHERE id=?').run(status,JSON.stringify({...attempted,nextAttemptAt}),message,iso(),row.id);
      notice(row.user_id,{type:retry?'resimulation_retry_scheduled':'resimulation_blocked',jobId:row.id,predictionId:attempted.predictionId,reason:message,nextAttemptAt});results.push({id:row.id,status,reason:message,nextAttemptAt});}
  }
  return{processed:results.length,jobs:results};
}
