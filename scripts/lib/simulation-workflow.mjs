import assert from 'node:assert/strict';

/** End-to-end transport helper. A queued receipt is never a completed model. */
export async function runSavedSimulation(client,input,{pollMs=2500,deadlineMs=600000,sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms)),now=Date.now,onProgress=()=>{}}={}){
 const started=now(),submitted=await client.call('simulations',input);
 if(![200,202].includes(submitted.status))throw Error(`Simulation submission HTTP ${submitted.status}: ${safeError(submitted.data?.error)}`);
 const receipt=submitted.data;
 if(!receipt||typeof receipt.id!=='string')throw Error('Simulation did not return a saved job identifier.');
 if(submitted.status===200&&!receipt.pending){
  if(receipt.status&&receipt.status!=='completed')throw Error('Synchronous simulation returned an unfinished job.');
  return{id:receipt.id,status:'completed',result:receipt,asynchronous:false};
 }
 let previousStatus=null;
 while(now()-started<=deadlineMs){
  const response=await client.call('simulations?id='+encodeURIComponent(receipt.id));
  if([502,503,504].includes(response.status)){await sleep(pollMs);continue;}
  if(response.status!==200)throw Error(`Saved simulation read HTTP ${response.status}: ${safeError(response.data?.error)}`);
  const job=response.data?.job;
  if(!job||job.id!==receipt.id)throw Error('Saved simulation identity does not match its receipt.');
  if(job.status!==previousStatus){onProgress({id:job.id,status:job.status});previousStatus=job.status;}
  if(job.status==='completed'){
   if(job.provenanceVerified!==true)throw Error('Completed simulation is missing a verified engine receipt.');
   if(!job.result||typeof job.result!=='object')throw Error('Completed simulation has no persisted result.');
   return{id:job.id,status:'completed',result:job.result,asynchronous:true,provenanceVerified:true};
  }
  if(['failed','blocked'].includes(job.status))return{id:job.id,status:job.status,error:safeError(job.error),asynchronous:true};
  if(!['queued','running'].includes(job.status))throw Error('Saved simulation has an unrecognized status.');
  await sleep(pollMs);
 }
 throw Error(`Saved simulation ${receipt.id} exceeded the ${deadlineMs}ms verification deadline; no completion is claimed. The saved job remains available.`);
}

function safeError(value){return typeof value==='string'?value.slice(0,1500):'No provider detail available.';}

/** Mechanical checks of actual engine output, not a calibration claim. */
export function validateCompleteGameResult(result,count){
 assert.equal(result.simulations,count);
 const approx=(actual,expected,label)=>assert.ok(Number.isFinite(actual)&&Math.abs(actual-expected)<1e-10,label);
 approx(result.homeWinProbability+result.awayWinProbability+result.tieProbability,1,'Win/tie probabilities must partition the complete games.');
 const distributions=[...Object.values(result.scoreDistributions),result.totalDistribution,result.marginDistribution];
 for(const distribution of distributions){
  assert.equal(distribution.histogram.reduce((n,bin)=>n+bin.count,0),count,'Every score distribution must contain every complete game.');
  approx(distribution.mean,distribution.histogram.reduce((n,bin)=>n+bin.value*bin.count,0)/count,'Histogram means must match their frequencies.');
 }
 approx(result.totalDistribution.mean,result.scoreDistributions[result.home].mean+result.scoreDistributions[result.away].mean,'Team scores must sum to the game total.');
 approx(result.marginDistribution.mean,result.scoreDistributions[result.home].mean-result.scoreDistributions[result.away].mean,'Team score difference must equal the margin.');
 assert.equal(result.jointOutcomes.reduce((n,row)=>n+row.count,0),count,'Joint contract outcomes must come from the complete-game sample.');
 const final=result.convergence.at(-1);assert.equal(final.simulations,count);approx(final.homeWinProbability,result.homeWinProbability,'Final convergence point must equal the actual estimate.');
 approx(final.monteCarloSE,Math.sqrt(result.homeWinProbability*(1-result.homeWinProbability)/count),'Monte Carlo error must use the actual complete-game count.');
 assert.ok(result.monteCarloInterval95[0]<=result.homeWinProbability&&result.homeWinProbability<=result.monteCarloInterval95[1]);
 for(const trace of result.representativeGames){
  assert.ok(trace.plays.length>50,'Expected a complete football-game trace.');assert.ok(trace.plays.some(p=>p.half===1)&&trace.plays.some(p=>p.half===2),'A representative game must span regulation halves.');
  assert.deepEqual(trace.plays.at(-1).score,trace.score,'Final play score must match the reported game score.');
  let previous=[0,0];
  for(const play of trace.plays){
   assert.ok(play.score.every((score,index)=>Number.isInteger(score)&&score>=previous[index]));
   assert.ok([0,2,3,6,7,8].includes(play.score[0]+play.score[1]-previous[0]-previous[1]),'A scoring event must follow the implemented NFL scoring rules.');
   previous=play.score;
   if(play.historicalEventAt)assert.ok(Date.parse(play.historicalEventAt)<Date.parse(result.evidenceCutoff),'Representative plays must use evidence available before the fitted cutoff.');
  }
  const sum=key=>Object.values(trace.players).reduce((n,player)=>n+(player[key]??0),0);
  assert.equal(sum('passingYards'),sum('receivingYards'),'Passing and receiving yards must arise from shared plays.');
  assert.equal(sum('completions'),sum('receptions'),'Completions and receptions must arise from shared plays.');
  assert.equal(sum('passingTouchdowns'),sum('receivingTouchdowns'),'Passing and receiving touchdowns must arise from shared plays.');
 }
 const parameter=result.uncertainty.parameterBootstrap;
 if(parameter){assert.equal(parameter.completeGames,parameter.replicates*parameter.gamesPerReplicate);assert.deepEqual(result.uncertainty.modelInterval,parameter.homeWinInterval95);assert.ok(parameter.historicalGameBlocks>=8);}
 else assert.equal(result.uncertainty.modelInterval,null,'Missing parameter uncertainty must remain explicitly unestimated.');
 return{completeGames:count,representativeGames:result.representativeGames.length,homeWinProbability:result.homeWinProbability,monteCarloInterval95:result.monteCarloInterval95,finalMonteCarloSE:final.monteCarloSE,parameterInterval95:parameter?.homeWinInterval95??null,parameterBootstrapGames:parameter?.completeGames??0,evidenceGames:result.evidence.games,evidencePlays:result.evidence.plays,availabilityVerified:result.evidence.availabilityVerified,engineVersion:result.engineVersion,modelVersion:result.modelVersion,inputDataVersion:result.inputDataVersion};
}

/** Read normalized source CSV without assuming quoted fields have no commas. */
export function receiverFromNormalizedCsv(csv,teams){
 const rows=parseCsv(csv);const columns=rows.shift()??[],offense=columns.indexOf('offense'),receiver=columns.indexOf('receiver_id');
 if(offense<0||receiver<0)return null;
 return rows.find(row=>teams.includes(row[offense])&&row[receiver])?.[receiver]??null;
}

function parseCsv(text){
 const rows=[];let row=[],cell='',quoted=false;
 for(let i=0;i<text.length;i++){
  const c=text[i];
  if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}
  else if(c===','&&!quoted){row.push(cell);cell='';}
  else if((c==='\r'||c==='\n')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);rows.push(row);row=[];cell='';}
  else cell+=c;
 }
 if(quoted)throw Error('Normalized CSV contains an unterminated quoted field.');
 if(cell||row.length){row.push(cell);rows.push(row);}
 return rows;
}
