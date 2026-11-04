import {wilson} from './model';
/** Exact shared-game frequencies from trusted evidence, never bookmaker prices. */
export function compareFreeProp(row:any,evidence:any){
 const unavailable=(reasonCode:string,reason:string,retryable=false)=>({modelProbability:null,calibratedProbability:null,expectedValue:null,reasonCode,state:'source_unavailable',retryable,reason});
 if(!row||!evidence)return unavailable('distribution_unavailable','A verified complete-game distribution has not been retrieved for this selection.',true);
 if(row.period!==null&&row.period!==undefined&&!['full','full_game','game'].includes(row.period))return unavailable('market_period_unsupported','The source specifies a partial-game market. Full-game outcomes cannot establish that probability.');
 if(!['NFL','CFB'].includes(row.sport)||row.sport!==evidence.sport)return unavailable('sport_mismatch','The source sport and simulation sport do not match.');
 if(!row.player?.id||row.player.id!==evidence.providerPlayerId)return unavailable('player_identity_mismatch','The stable player ID does not match the verified simulation crosswalk.');
 if(row.eventId!==evidence.providerEventId||Date.parse(row.kickoff)!==Date.parse(evidence.kickoff))return unavailable('event_identity_mismatch','The provider event or kickoff does not match this simulation.');
 if(Date.parse(row.kickoff)<=Date.now())return unavailable('pregame_only','This pregame distribution is historical. A verified in-game model is unavailable.');
 if(evidence.stale!==false)return unavailable('inputs_stale','Verified inputs changed; a current simulation is required.',true);
 if(!Number.isInteger(evidence.simulations)||evidence.simulations<10000||evidence.simulations>100000)return unavailable('simulation_count_unavailable','The requested complete-game count could not be verified.',true);
 if(!['Over','Under'].includes(row.side)||row.threshold===null||row.threshold===undefined||String(row.threshold).trim()===''||!Number.isFinite(Number(row.threshold)))return unavailable('exact_threshold_or_selection_unsupported','The provider did not supply an exact supported Over/Under threshold. Selection-only touchdown prices are not assigned an invented threshold or settlement rule.');
 if(evidence.statistic!==row.statistic)return unavailable('statistic_mapping_mismatch','The simulation statistic does not match the source market category.');
 const histogram=evidence.histogram;
 if(!Array.isArray(histogram)||histogram.some((r:any)=>!Number.isFinite(r.value)||!Number.isSafeInteger(r.count)||r.count<0)||histogram.reduce((s:number,r:any)=>s+r.count,0)!==evidence.simulations)return unavailable('distribution_integrity_failure','The stored outcome frequencies do not reconcile to the completed game count.');
 const n=evidence.simulations,line=Number(row.threshold),hits=histogram.filter((r:any)=>row.side==='Over'?r.value>line:r.value<line).reduce((s:number,r:any)=>s+r.count,0),push=histogram.filter((r:any)=>r.value===line).reduce((s:number,r:any)=>s+r.count,0);
 return {modelProbability:hits/n,successfulSimulations:hits,pushes:push,monteCarloInterval95:wilson(hits,n),pushProbability:push/n,calibratedProbability:null,expectedValue:null,simulations:n,modelVersion:evidence.modelVersion,reason:'Raw full-game statistical threshold reference only. Current roster, team injury and weather adjustments are incomplete. Book participation, overtime, push, fee and settlement rules remain unverified.'};
}
