/** Pure distribution scoring. Sampling intervals are not model uncertainty.
 * All scores use frozen integer-frequency distributions from complete games. */
import type {Histogram,DistributionComparison,FrozenSimulation,FinalReality,GameEvaluation} from './types';
export const LEARNING_PROTOCOL='gall-frozen-full-game-distribution-14.0.0';
export function checkedHistogram(value:any,n:number):Histogram{
 if(!Number.isSafeInteger(n)||n<1||n>100000||!Array.isArray(value)||!value.length||value.length>100001)throw Error('Completed-game histogram unavailable.');
 const seen=new Set<number>();let sum=0;
 for(const b of value){if(!Number.isSafeInteger(b.value)||!Number.isSafeInteger(b.count)||b.count<1||seen.has(b.value))throw Error('Invalid or duplicate distribution bin.');seen.add(b.value);sum+=b.count;}
 if(sum!==n)throw Error('Distribution does not reconcile to the complete-game count.');
 return value.map(b=>({value:b.value,count:b.count})).sort((a,b)=>a.value-b.value);
}
export function distributionComparison(value:any,n:number,actual:number):DistributionComparison{
 if(!Number.isFinite(actual))throw Error('Verified actual statistic unavailable.');const bins=checkedHistogram(value,n);
 const q=(p:number)=>{const target=Math.max(1,Math.ceil(n*p));let c=0;for(const b of bins){c+=b.count;if(c>=target)return b.value;}return bins[bins.length-1].value;};
 const mean=bins.reduce((s,b)=>s+b.value*b.count,0)/n;
 // E|X-y| - .5 E|X-X'|; prefix sums avoid an O(bins²) pairwise matrix.
 let prefixN=0,prefixSum=0,pairs=0,abs=0;for(const b of bins){pairs+=b.count*(b.value*prefixN-prefixSum);prefixN+=b.count;prefixSum+=b.value*b.count;abs+=b.count*Math.abs(b.value-actual);}
 return{mean,median:q(.5),actual,signedError:mean-actual,absoluteError:Math.abs(mean-actual),crps:Math.max(0,abs/n-pairs/(n*n)),intervals:Object.fromEntries([.5,.8,.9,.95].map(level=>{const lower=q((1-level)/2),upper=q((1+level)/2);return[String(Math.round(level*100)),{lower,upper,covered:actual>=lower&&actual<=upper}];})),histogram:bins};
}
export function evaluateSimulation(f:FrozenSimulation,actual:FinalReality,meta:{forecastId:string;actualId:string;archivedAt:string;mode:'pregame'|'retrospective'},now=new Date()):GameEvaluation{
 const g=f.game,a=actual.game,r=f.result,n=r.simulations;
 if(actual.status!=='final'||g.sport!==a.sport||g.id!==a.id||g.home.id!==a.home.id||g.away.id!==a.away.id||Date.parse(g.startTime)!==Date.parse(a.startTime)||g.season!==a.season||g.week!==a.week)throw Error('Final game identity does not match the frozen forecast.');
 if(r.home!==g.home.id||r.away!==g.away.id||Date.parse(r.eventStart)!==Date.parse(g.startTime)||r.modelVersion!==f.modelVersion||!Number.isSafeInteger(n)||n<10000||n>100000)throw Error('Simulation identity or complete-game count is invalid.');
 if(!actual.sources.length||actual.sources.some(s=>!s.url.startsWith('https://')||!s.version||!Number.isFinite(Date.parse(s.collectedAt)))||!Number.isFinite(Date.parse(actual.verifiedAt))||Date.parse(actual.verifiedAt)<Date.parse(g.startTime)||Date.parse(actual.verifiedAt)>now.getTime()+60000)throw Error('Verified final-result provenance unavailable.');
 for(const v of Object.values(actual.scores))if(!Number.isSafeInteger(v)||v<0||v>300)throw Error('Verified final scores unavailable.');
 if(!Number.isFinite(Date.parse(meta.archivedAt))||!Number.isFinite(Date.parse(f.predictedAt))||!Number.isFinite(Date.parse(g.startTime)))throw Error('Verified forecast chronology unavailable.');
 if(meta.mode==='pregame'&&(f.retrospective||Date.parse(meta.archivedAt)>=Date.parse(g.startTime)||Date.parse(f.predictedAt)>Date.parse(meta.archivedAt)||Date.parse(f.predictedAt)>=Date.parse(g.startTime)))throw Error('Forecast was not archived before kickoff.');
 const home=distributionComparison(r.scoreDistributions?.[g.home.id]?.histogram,n,actual.scores.home),away=distributionComparison(r.scoreDistributions?.[g.away.id]?.histogram,n,actual.scores.away),total=distributionComparison(r.totalDistribution?.histogram,n,actual.scores.home+actual.scores.away),margin=distributionComparison(r.marginDistribution?.histogram,n,actual.scores.home-actual.scores.away);
 const probabilities={home:0,away:0,tie:0};for(const b of margin.histogram)probabilities[b.value>0?'home':b.value<0?'away':'tie']+=b.count/n;
 for(const[key,field]of [['home','homeWinProbability'],['away','awayWinProbability'],['tie','tieProbability']] as const)if(typeof r[field]!=='number'||Math.abs(probabilities[key]-r[field])>1e-9)throw Error('Win probabilities disagree with the shared game-margin distribution.');
 if(g.sport==='CFB'&&(actual.scores.home===actual.scores.away||probabilities.tie>0))throw Error('College overtime evidence cannot contain final ties.');
 const winner=actual.scores.home>actual.scores.away?'home':actual.scores.home<actual.scores.away?'away':'tie';const predicted=(Object.keys(probabilities) as Array<keyof typeof probabilities>).reduce((best,k)=>probabilities[k]>probabilities[best]?k:best,'home');
 const players:GameEvaluation['players']=[];let pending=0;
 const catalog=Array.isArray(f.research.playerCatalog)?new Map(f.research.playerCatalog.map((v:any)=>[v.id??v.playerId,v])):new Map(Object.entries(f.research.playerCatalog??{}));
 for(const[id,stats]of Object.entries(r.players??{}) as Array<[string,Record<string,any>]>){const observed=actual.players[id],info:any=catalog.get(id);for(const[stat,dist]of Object.entries(stats)){const v=observed?.stats?.[stat];if(!observed?.participationVerified||v===null||v===undefined||!Number.isFinite(v)||info?.team&&info.team!==observed.teamId){pending++;continue;}players.push({id,name:observed.name||info?.name||id,teamId:observed.teamId,stat,comparison:distributionComparison(dist?.histogram,n,v)});}}
 const brier=(Object.keys(probabilities) as Array<keyof typeof probabilities>).reduce((s,k)=>s+(probabilities[k]-Number(k===winner))**2,0),logLoss=-Math.log(Math.max(1e-15,probabilities[winner]));
 const calibration=f.homeWinCalibration&&Number.isFinite(f.homeWinCalibration.probability)&&f.homeWinCalibration.probability>=0&&f.homeWinCalibration.probability<=1&&Date.parse(f.homeWinCalibration.availableAt)<=Date.parse(f.predictedAt)?f.homeWinCalibration:null;
 return{schemaVersion:1,protocol:LEARNING_PROTOCOL,forecastId:meta.forecastId,actualId:meta.actualId,sport:g.sport,game:g,modelVersion:f.modelVersion,predictedAt:f.predictedAt,archivedAt:meta.archivedAt,mode:meta.mode,simulations:n,evaluatedAt:now.toISOString(),home,away,total,margin,winner:{predicted,actual:winner,correct:predicted===winner,probabilities,brier,logLoss},players,pendingPlayerStatistics:pending,sources:actual.sources,homeWinCalibration:calibration,limitations:[...actual.limitations,'Prediction intervals describe the frozen simulated distribution; parameter and source uncertainty remain separate.','One unlikely result does not establish miscalibration. Repeated versions of the same game are correlated.','Winner Brier score uses the three mutually exclusive home/away/tie classes (range 0–2).']};
}
/** One final pregame version per game AND model. Retrospective audits are a
 * separate panel and are never pooled into prospective reliability metrics. */
export function performanceSummary(evaluations:GameEvaluation[]){
 const latest=new Map<string,GameEvaluation>();for(const e of evaluations){if(e.mode!=='pregame')continue;const key=[e.sport,e.game.id,e.modelVersion].join(':');const prior=latest.get(key);if(!prior||Date.parse(e.archivedAt)>Date.parse(prior.archivedAt)||e.forecastId===prior.forecastId&&Date.parse(e.evaluatedAt)>Date.parse(prior.evaluatedAt))latest.set(key,e);}
 const all=[...latest.values()],mean=(v:number[])=>v.length?v.reduce((a,b)=>a+b,0)/v.length:null;
 const metric=(rows:GameEvaluation[])=>{const scores=rows.flatMap(e=>[e.home,e.away]),players=rows.flatMap(e=>e.players);return{games:rows.length,playerPredictions:players.length,winnerAccuracy:mean(rows.map(e=>Number(e.winner.correct))),brier:mean(rows.map(e=>e.winner.brier)),logLoss:mean(rows.map(e=>e.winner.logLoss)),scoreMAE:mean(scores.map(e=>e.absoluteError)),scoreRMSE:scores.length?Math.sqrt(mean(scores.map(e=>e.signedError**2))!):null,totalMAE:mean(rows.map(e=>e.total.absoluteError)),marginMAE:mean(rows.map(e=>e.margin.absoluteError)),scoreCRPS:mean(scores.map(e=>e.crps)),playerMAEByStat:Object.fromEntries([...new Set(players.map(p=>p.stat))].map(stat=>[stat,mean(players.filter(p=>p.stat===stat).map(p=>p.comparison.absoluteError))])),coverage:Object.fromEntries(['50','80','90','95'].map(k=>[k,mean(scores.map(s=>Number(s.intervals[k].covered)))])),homeWinCalibration:Array.from({length:10},(_,i)=>{const group=rows.filter(e=>Math.min(9,Math.floor(e.winner.probabilities.home*10))===i);return{lower:i/10,upper:(i+1)/10,n:group.length,predicted:mean(group.map(e=>e.winner.probabilities.home)),observed:mean(group.map(e=>Number(e.winner.actual==='home')))};})};};
 return{protocol:LEARNING_PROTOCOL,selection:'Final archived pregame version per game and model; historical reruns excluded.',overall:metric(all),byModel:Object.fromEntries([...new Set(all.map(e=>e.modelVersion))].map(v=>[v,metric(all.filter(e=>e.modelVersion===v))])),retrospectiveGames:new Set(evaluations.filter(e=>e.mode==='retrospective').map(e=>e.game.id)).size,updatedAt:new Date().toISOString(),promotion:'No improvement or model promotion is implied by these descriptive metrics.'};
}
