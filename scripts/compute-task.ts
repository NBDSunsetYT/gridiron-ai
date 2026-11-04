/** One child process per admitted task. The Python supervisor enforces lifetime. */
import {taskSchema,computeOperation} from '../lib/compute/queue';
import {finishDeferred} from '../lib/compute/policy';
async function main(){
 if(process.env.VERCEL||process.env.GRIDIRON_COMPUTE_ROLE!=='worker')throw Error('Controlled local/Render worker role required');
 let text='';for await(const chunk of process.stdin){text+=chunk;if(text.length>14000)throw Error('Bounded task required');}
 const job=JSON.parse(text),task=taskSchema.parse(job.task);
 if(task.kind==='game'){
  if(task.sport==='CFB'){const m=await import('../lib/college-football/service');const d=await m.analyzeCollegeGame(task.gameId,task.simulations);if(d.analysis?.status!=='completed')throw Error('CFB evidence unavailable');}
  else if(task.sport==='NBA'){const m=await import('../lib/nba/service');const d=await m.analyzeNBAGame(new Request('http://127.0.0.1/worker'),task.gameId,task.simulations);if(!d.analysis?.result)throw Error('NBA evidence unavailable');}
  else{const m=await import('../lib/public-nfl/service');await m.analyzePublicGame(task.gameId,task.simulations);await finishDeferred();const d=await m.publicGameDetail(task.gameId,task.simulations);if(d.analysis?.status!=='completed')throw Error('NFL evidence unavailable');}
 }else if(task.kind==='probability'){
  const m=await import('../lib/probability/jobs');const receipt=await m.requestProbabilityJob(new Request('http://127.0.0.1/worker'),task.request.target,task.request.simulations);await finishDeferred();if((await m.readProbabilityJob(receipt.jobId)).status!=='ready')throw Error('Requested probability remains unavailable');
 }else if(task.kind==='prop_scan'){
  await(await import('../lib/player-props/service')).executePropRun(task.runId,Date.now());
 }else{
  // Refresh metadata once per operator cycle; at most ONE existing automatic
  // research job consumes a 10k reservation. No visitor or nested cron fan-out.
  await(await import('../lib/public-nfl/service')).loadSchedule();
  await(await import('../lib/college-football/service')).refreshCollegeResearch();
  const {loadPropBoard}=await import('../lib/probability/market-board');
  const auto=await import('../lib/probability/automatic-props');
  for(const sport of ['NFL','CFB'] as const){const board=await loadPropBoard(sport,0);await auto.automaticPropResearch(sport,board);}
  await auto.drainAutomaticProps(1);
  await(await import('../lib/learning/service')).refreshFootballLearning();
 }
 await finishDeferred();
 // Receipt contains no raw input, credentials, probabilities or private data.
 console.log(JSON.stringify({completed:true,id:job.id,kind:task.kind}));
}
void main().catch(()=>{console.error('Controlled research task did not finish; durable inputs and previous forecasts are preserved.');process.exitCode=1;});
