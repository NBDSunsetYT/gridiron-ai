/** Deterministic, read-only evidence audit. It never repairs history or creates a probability. */
type Row=Record<string,any>;
export type AuditIssue={code:string;severity:'block'|'warning'|'info';message:string;entityId?:string;source?:string;timestamp?:string};
const finite=(v:unknown)=>typeof v==='number'&&Number.isFinite(v);
const stamp=(v:unknown)=>typeof v==='string'&&Number.isFinite(Date.parse(v))?Date.parse(v):NaN;
function decode(value:unknown){try{return typeof value==='string'?JSON.parse(value):value;}catch{return null;}}
export function auditWorkspace(input:{quotes?:Row[];contracts?:Row[];predictions?:Row[];injuries?:Row[];simulations?:Row[];performance?:Row;models?:Row[]},now=new Date()){
 const quotes=input.quotes||input.contracts||[],predictions=input.predictions||[],injuries=input.injuries||[],simulations=input.simulations||[],nowMs=now.getTime();
 const decisions=predictions.map(pred=>{
  const issues:AuditIssue[]=[],id=pred.id||pred.contractId||'unknown';
  const add=(code:string,severity:AuditIssue['severity'],message:string,extra:Partial<AuditIssue>={})=>issues.push({code,severity,message,entityId:id,...extra});
  const quote=quotes.find(q=>q.id===pred.quoteId)||quotes.find(q=>q.contractId===pred.contractId);
  if(!quote)add('contract_missing','block','The exact contract snapshot cannot be retrieved.');
  else{
   if(!quote.contractId||!quote.eventId||!quote.event)add('contract_identity_missing','block','Contract and event identifiers and event text are required.');
   if(!finite(quote.threshold)||!['gt','gte','lt','lte','eq'].includes(quote.operator))add('threshold_invalid','block','The exact finite threshold and comparison operator are unavailable.');
   if(typeof quote.settlementRule!=='string'||quote.settlementRule.length<10||!quote.rulesUrl)add('settlement_rules_missing','block','Settlement terms and their source citation are missing.');
   const definition=quote.settlementDefinition;
   if(!definition||!definition.kind||!definition.home||!definition.away||definition.home===definition.away)add('structured_identity_missing','block','Verified structured market kind and distinct matchup team IDs are required to match a generated estimate.');
   else if(definition.kind==='player'&&(!definition.playerId||!definition.stat))add('player_identity_missing','block','A player contract requires the exact player ID and statistic.');
   else if(definition.kind==='team_total'&&!['home','away'].includes(definition.team))add('team_identity_missing','block','A team-total contract must identify the home or away team.');
   if(!quote.sourceUrl)add('quote_provenance_missing','block','The source of the recorded price is unavailable.');
   if(!Number.isFinite(stamp(quote.quotedAt)))add('quote_timestamp_missing','block','The market observation timestamp is invalid.');
   else if(stamp(quote.quotedAt)>nowMs+60000)add('quote_from_future','block','The market observation is in the future.');
   else if(nowMs-stamp(quote.quotedAt)>120000)add('quote_stale','block','The quoted price is older than two minutes and cannot be treated as a current offer.',{timestamp:quote.quotedAt});
   for(const field of ['yesAskCents','noAskCents','entryFeeCents','winFeeCents'])if(quote[field]===undefined||quote[field]===null||!Number.isFinite(Number(quote[field])))add('price_or_fees_missing','block','Exact quoted prices and fees are required; no zero fee is inferred.');
   if(quote.source==='manual_verified')add('manual_verification','info','This source was verified by the user. The report content and executable price have not been independently fetched.',{source:quote.sourceUrl,timestamp:quote.quotedAt});
  }
  const eventStart=stamp(pred.eventStart||quote?.eventStart);
  if(!Number.isFinite(eventStart))add('event_time_missing','block','A valid event start timestamp is required.');
  else if(eventStart<=nowMs)add('event_started','block','This is a historical or in-progress event. The archived estimate cannot be published as a new pre-event forecast.');
  if(!Number.isFinite(stamp(pred.asOf))||Number.isFinite(eventStart)&&stamp(pred.asOf)>=eventStart)add('prediction_time_invalid','block','The prediction input cutoff must be known and strictly before event start.');
  if(pred.auditStatus==='retrospective_import')add('retrospective_import','warning','This estimate was imported retrospectively and is excluded from prospective accuracy claims.');
  const p=pred.yesProbability??pred.probability;
  if(!finite(p)||p<=0||p>=1)add('probability_invalid','block','A finite probability strictly inside zero and one is required; finite simulation counts cannot establish certainty.');
  else if(p<.005||p>.995)add('extreme_tail','warning','This estimate is in an extreme tail. Small sampling error does not establish tail calibration.');
  if(!pred.modelVersion)add('model_version_missing','block','The model version is missing.');
  if(!pred.inputsHash&&!pred.computedInputsHash)add('input_version_missing','block','The immutable input-data version/hash is unavailable.');
  if(pred.stale)add('prediction_stale','block','Changed or expired inputs marked this prediction stale; it requires a new archived run.');
  for(const version of pred.injuryVersions||[]){
   const record=injuries.filter(r=>r.entityKey===version.entityKey).sort((a,b)=>stamp(b.checkedAt)-stamp(a.checkedAt))[0];
   if(!record){add('injury_evidence_missing','block',`Referenced injury evidence ${version.entityKey} is unavailable.`);continue;}
   if(record.factsHash!==version.factsHash)add('injury_changed','block',`The recorded availability assumptions changed for ${record.player||version.entityKey}.`,{source:record.sourceUrl,timestamp:record.checkedAt});
   if(!Number.isFinite(stamp(record.checkedAt))||nowMs-stamp(record.checkedAt)>24*3600000)add('injury_stale','block',`The latest injury check for ${record.player||version.entityKey} is missing or older than 24 hours.`,{timestamp:record.checkedAt});
   if(['questionable','doubtful','unknown'].includes(record.status)&&!record.availability)add('availability_uncertain','warning','Uncertain player availability has no supported numerical cohort weights. It must not be silently treated as active.');
  }
  const simulationId=pred.evidence?.simulationId;
  if(simulationId){
   const job=simulations.find(r=>r.id===simulationId),result=decode(job?.result);
   if(!job||job.status!=='completed'||!result)add('simulation_unavailable','block','The referenced simulation is missing, incomplete or failed.');
   else{
    if(quote?.settlementDefinition&&(quote.settlementDefinition.home!==result.home||quote.settlementDefinition.away!==result.away))add('simulation_matchup_mismatch','block','The simulated home/away team identities do not match the verified contract matchup.');
    if(result.modelVersion!==pred.modelVersion)add('model_version_mismatch','block','The saved prediction and completed simulation have different model versions.');
    const mass=(result.homeWinProbability??NaN)+(result.awayWinProbability??NaN)+(result.tieProbability??NaN);
    if(!Number.isFinite(mass)||Math.abs(mass-1)>1e-6)add('probabilities_inconsistent','block','Home, away and tie probabilities do not reconcile to one.');
    const n=result.simulations;if(!Number.isSafeInteger(n)||n<1)add('simulation_count_invalid','block','The completed-game count is unavailable.');
    else if(n<10000)add('small_monte_carlo_run','warning','This custom run contains fewer than 10,000 games. Inspect Monte Carlo error before comparing close probabilities.');
    if(Object.keys(result.scoreDistributions||{}).length!==2)add('score_distributions_missing','block','Both team score distributions are required for a coherent completed-game run.');
    for(const dist of Object.values(result.scoreDistributions||{}) as Row[]){const count=(dist.histogram||[]).reduce((s:number,r:Row)=>s+Number(r.count),0);if(!finite(count)||Math.abs(count-n)>Math.max(1e-6,n*1e-8))add('distribution_inconsistent','block','A score histogram does not reconcile with the generated game count.');}
    const contract=(result.contracts||[]).find((r:Row)=>r.id===pred.contractId);
    if(!contract)add('simulation_contract_missing','block','The exact contract identifier was not evaluated in this simulation.');
    else{
     if(finite(p)&&Math.abs(p-contract.probability)>1e-9)add('generated_probability_mismatch','block','The saved probability differs from the exact completed-run contract result.');
     const d=quote?.settlementDefinition,s=contract.settlement;
     if(d&&s){for(const field of ['kind','playerId','stat','team','threshold','direction','equality'])if(d[field]!==s[field]){add('simulation_settlement_mismatch','block','The simulated market, player/statistic or settlement definition differs from the verified contract.');break;}}
    }
    if(!result.uncertainty?.modelInterval)add('model_uncertainty_unestimated','warning','Parameter/model uncertainty has not been estimated. Monte Carlo intervals cover only finite-run randomness.');
    const checkpoints=result.convergence||[];if(checkpoints.length<2)add('convergence_unavailable','warning','At least two convergence checkpoints are required to inspect numerical stability.');
    else{const last=checkpoints.at(-1),previous=checkpoints.at(-2),error=Math.abs(last.homeWinProbability-previous.homeWinProbability);if(finite(error)&&finite(last.monteCarloSE)&&error>Math.max(.02,4*last.monteCarloSE))add('simulation_unstable','warning','The final convergence checkpoints changed materially relative to reported Monte Carlo noise.');}
   }
  }else add('supplied_estimate','warning','This probability is a supplied estimate rather than a completed signed game simulation. Its original model validation must be reviewed.');
  const model=(input.models||[]).find(m=>m.version===pred.modelVersion||m.modelVersion===pred.modelVersion);
  if(!model?.promotionEligible)add('calibration_not_validated','warning','No independently evaluated chronological model promotion record supports this model version. The estimate remains research-only.');
  const status=issues.some(i=>i.severity==='block')?'withheld':issues.some(i=>i.severity==='warning')?'research_only':'supported';
  return{predictionId:id,contractId:pred.contractId,modelVersion:pred.modelVersion,status,withheld:status==='withheld',publishable:status==='supported',issues};
 });
 return{auditedAt:now.toISOString(),summary:{predictions:decisions.length,withheld:decisions.filter(d=>d.status==='withheld').length,researchOnly:decisions.filter(d=>d.status==='research_only').length,supported:decisions.filter(d=>d.status==='supported').length},decisions,policy:'Read-only deterministic evidence checks. A passing structural audit is not evidence of profitability. Missing calibration or model uncertainty prevents a supported/publishable status.',sources:{quotes:quotes.length,injuryRecords:injuries.length,simulationRecords:simulations.length},emptyMessage:decisions.length?null:'No saved predictions are available to audit. Import exact evidence and save a prediction; the auditor never creates one.'};
}
