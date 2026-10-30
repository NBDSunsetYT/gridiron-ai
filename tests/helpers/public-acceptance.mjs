import assert from 'node:assert/strict';

/** Acceptance checks for published football research, independent of UI labels.
 * These do not establish predictive calibration or justify a real wager. */
export function assertNoPrivateResearchFields(value){
 const forbidden=new Set(['user_id','email','password','password_hash','access_token','refresh_token','service_role','serviceRoleKey','ledger','journal','postings','wagers','transactions','preferences','fittedModel','modelArtifact','trainingRows','csv','signature','inputProof','resultProof']);
 const visit=(node,path='response')=>{
  if(!node||typeof node!=='object')return;
  for(const[key,item]of Object.entries(node)){
   assert.ok(!forbidden.has(key),`Private or raw fitted evidence field leaked into ${path}.${key}`);
   visit(item,path+'.'+key);
  }
 };
 visit(value);
}

export function assertPublishedSource(source){
 assert.ok(source&&typeof source.name==='string'&&source.name.length>0,'A research source needs its name.');
 assert.ok(['https:','http:'].includes(new URL(source.url).protocol),'Source citations must be actual HTTP(S) references.');
 assert.ok(Number.isFinite(Date.parse(source.collectedAt)),'A source collection timestamp is required.');
 assert.ok(['available','partial','unavailable'].includes(source.status),'Source availability must be explicit.');
}

export function assertPublicGameResult(result,count=10000){
 assert.equal(result.simulations,count,'The actual engine must run the requested number of complete games.');
 const close=(a,b,label)=>assert.ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-7,label);
 for(const p of [result.homeWinProbability,result.awayWinProbability,result.tieProbability])assert.ok(Number.isFinite(p)&&p>=0&&p<=1,'All estimated probabilities must be finite and bounded.');
 close(result.homeWinProbability+result.awayWinProbability+result.tieProbability,1,'Win/tie events must partition the game sample.');
 assert.ok(typeof result.home==='string'&&typeof result.away==='string'&&result.home!==result.away);
 const histogram=(value,label)=>{
  assert.ok(value?.histogram?.length,`${label} distribution needs its observed simulated frequencies.`);
  for(const row of value.histogram)assert.ok(Number.isFinite(row.value)&&Number.isInteger(row.count)&&row.count>=0,`${label} frequencies must be finite nonnegative counts.`);
  assert.equal(value.histogram.reduce((n,row)=>n+row.count,0),count,`${label} must contain all complete games.`);
  close(value.mean,value.histogram.reduce((n,row)=>n+row.value*row.count,0)/count,`${label} mean must reconcile with its histogram.`);
 };
 for(const team of [result.home,result.away])histogram(result.scoreDistributions?.[team],team+' score');
 histogram(result.totalDistribution,'Total');histogram(result.marginDistribution,'Margin');
 close(result.homeWinProbability,result.marginDistribution.histogram.filter(row=>row.value>0).reduce((n,row)=>n+row.count,0)/count,'Published win probability must count the actual simulated winning margins.');
 close(result.tieProbability,result.marginDistribution.histogram.filter(row=>row.value===0).reduce((n,row)=>n+row.count,0)/count,'Published tie probability must count the actual simulated tied games.');
 close(result.totalDistribution.mean,result.scoreDistributions[result.home].mean+result.scoreDistributions[result.away].mean,'Team scoring must produce the same game total.');
 close(result.marginDistribution.mean,result.scoreDistributions[result.home].mean-result.scoreDistributions[result.away].mean,'Team scoring must produce the same game margin.');
 assert.ok(result.players&&Object.keys(result.players).length>0,'Player distributions must emerge from the simulated games.');
 const playerMeans={};
 for(const[name,stats]of Object.entries(result.players))for(const[stat,distribution]of Object.entries(stats)){
  histogram(distribution,`${name} ${stat}`);playerMeans[stat]=(playerMeans[stat]??0)+distribution.mean;
 }
 const withheld=result.publicPlayerForecastsWithheld??{};
 for(const[id,reason]of Object.entries(withheld)){
  assert.ok(typeof reason==='string'&&reason.length>0,'Every withheld player forecast needs its evidence reason.');
  assert.ok(!Object.hasOwn(result.players,id),'A withheld player must not retain an unsupported public forecast.');
 }
 if(Object.keys(withheld).length)assert.ok(result.publicLimitations?.some(value=>/withheld/i.test(value)),'Partial player coverage must be explicit rather than silently changing the game sample.');
 else{
  close(playerMeans.passingYards,playerMeans.receivingYards,'Passing and receiving yards must come from shared plays.');
  close(playerMeans.completions,playerMeans.receptions,'Completions and receptions must come from shared plays.');
  close(playerMeans.passingTouchdowns,playerMeans.receivingTouchdowns,'Passing and receiving touchdowns must come from shared plays.');
 }
 const convergence=result.convergence?.at(-1);assert.equal(convergence?.simulations,count);
 close(convergence.homeWinProbability,result.homeWinProbability,'Final convergence must equal the published estimate.');
 close(convergence.monteCarloSE,Math.sqrt(result.homeWinProbability*(1-result.homeWinProbability)/count),'Monte Carlo error must use the completed sample count.');
 assert.ok(result.monteCarloInterval95?.[0]<=result.homeWinProbability&&result.homeWinProbability<=result.monteCarloInterval95?.[1]);
 if(result.contracts?.length)assert.equal(result.jointOutcomes.reduce((n,row)=>n+row.count,0),count,'Quoted contracts must settle together within those complete games.');
 else assert.equal(result.jointOutcomes?.length??0,0,'Unavailable contracts must not be invented to fill a joint-market table.');
 assert.ok(result.representativeGames?.length>0,'At least one generated full game must be inspectable.');
 for(const game of result.representativeGames){
  assert.ok(game.plays.length>50&&game.plays.some(p=>p.half===1)&&game.plays.some(p=>p.half===2),'A complete game must include both regulation halves.');
  assert.deepEqual(game.plays.at(-1).score,game.score,'The last play and final score must agree.');
  let previous=[0,0];
  for(const play of game.plays){assert.ok(play.score.every((score,index)=>Number.isInteger(score)&&score>=previous[index]));assert.ok([0,2,3,6,7,8].includes(play.score[0]+play.score[1]-previous[0]-previous[1]));previous=play.score;}
  const sum=stat=>Object.values(game.players).reduce((n,player)=>n+(player[stat]??0),0);
  close(sum('passingYards'),sum('receivingYards'),'Shared trace passing and receiving yard identities must agree.');
  close(sum('completions'),sum('receptions'),'Shared trace completions and receptions must agree.');
 }
 assert.ok(result.modelVersion&&result.engineVersion&&result.inputDataVersion&&Number.isFinite(Date.parse(result.evidenceCutoff)),'Engine version and data provenance are required.');
 return{completeGames:count,players:Object.keys(result.players).length,withheldPlayers:Object.keys(withheld).length,representativeGames:result.representativeGames.length,modelVersion:result.modelVersion,inputDataVersion:result.inputDataVersion,homeWinProbability:result.homeWinProbability};
}

export function assertPublicGameDetail(detail,{completed=false}={}){
 assertNoPrivateResearchFields(detail);
 assert.ok(detail.game?.id&&detail.game.home?.abbreviation&&detail.game.away?.abbreviation);
 assert.ok(Number.isFinite(Date.parse(detail.game.startTime)));
 assert.ok(detail.sources?.length>0);for(const source of detail.sources)assertPublishedSource(source);
 for(const key of ['injuries','markets']){
  const coverage=detail[key];assert.ok(['available','partial','unavailable'].includes(coverage?.status));assert.ok(Array.isArray(coverage.items));assert.ok(Number.isFinite(Date.parse(coverage.checkedAt)));assert.ok(coverage.message?.length>0);
  if(coverage.status==='unavailable')assert.equal(coverage.items.length,0,`${key} must not fabricate missing evidence.`);
 }
 for(const injury of detail.injuries.items){assert.ok(['confirmed_unavailable','uncertain','reported_active','unknown'].includes(injury.availability));assert.ok(injury.sourceUrl&&Number.isFinite(Date.parse(injury.checkedAt)));if(injury.availability==='uncertain')assert.ok(!injury.officialConfirmed||!/^out|inactive$/i.test(injury.status),'Uncertain availability must not be silently converted into confirmed inactivity.');}
 for(const contract of detail.markets.items){
  assert.ok(contract.quoteVerified===true&&contract.verified===true&&typeof contract.provider==='string','Displayed market prices need an explicit provider and verification boundary.');
  assert.equal(new URL(contract.sourceUrl).protocol,'https:');assert.ok(Number.isFinite(Date.parse(contract.observedAt)),'An observed quote must retain its collection time.');
  assert.ok(typeof contract.settlementRule==='string'&&contract.settlementRule.length>20,'A displayed contract needs exact retained settlement terms.');
  if(contract.quotedAt===null)assert.ok(contract.quoteTimestampMeaning?.length>0,'An absent exchange quote timestamp must not be invented.');
  assert.ok([contract.yesAskCents,contract.yesBidCents].some(value=>value!==undefined&&Number.isFinite(Number(value))&&Number(value)>0&&Number(value)<=100),'A displayed quote must contain a valid observed binary price.');
  if(contract.fees?.calculationStatus!=='verified')assert.equal(contract.expectedNetValueAfterFeesCents,null,'Unknown exact fees must withhold a net-value claim.');
  if(contract.provider!=='DraftKings Predictions')assert.equal(contract.draftKingsEquivalent,false,'An alternative exchange must not be mislabeled as an equivalent DraftKings contract without its rules.');
 }
 if(completed){
  assert.equal(detail.analysis?.status,'completed');assert.ok(detail.analysis?.result);
  const summary=detail.analysis.summary??detail.summary;assert.ok(summary?.text?.length>0&&Array.isArray(summary.citations)&&summary.citations.length>0,'An analysis requires cited research explanation.');
  assert.ok(typeof summary.generatedByAI==='boolean');assert.ok(summary.generatedByAI?summary.method==='openai':summary.method==='evidence_brief','Source-based summaries must not pretend to be language-model generation.');
  for(const source of summary.citations)assertPublishedSource(source);
  return assertPublicGameResult(detail.analysis.result,detail.analysis.simulations);
 }
 return null;
}
