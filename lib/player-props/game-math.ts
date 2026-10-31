import Decimal from 'decimal.js';
import {wilson} from '../model';
import {sha} from '../public-nfl/sources';
import type {PublicGameDetail} from '../public-nfl/types';
import type {PropMarketContract} from './market-types';
import type {PropDistribution,PropResearch} from './types';
import {recheckPropMarketFreshness,canonicalPropTeam} from './normalize';
import {thresholdHit,valueProp} from './math';
import {gameParameterInterval} from './game-samples';

function exactHistogram(value:any,n:number,minimum:number,maximum:number):PropDistribution|null{
 if(!Array.isArray(value?.histogram)||!Number.isInteger(n)||n<10000||n>100000)return null;
 const seen=new Set<number>();let count=0,total=0;for(const row of value.histogram){if(!Number.isInteger(row?.value)||row.value<minimum||row.value>maximum||!Number.isInteger(row.count)||row.count<0||seen.has(row.value))return null;seen.add(row.value);count+=row.count;total+=row.value*row.count;}
 if(count!==n)return null;const histogram=[...value.histogram].sort((a,b)=>a.value-b.value),quantile=(p:number)=>{let c=0;for(const row of histogram){c+=row.count;if(c>=Math.ceil(n*p))return row.value;}return null;};
 return{histogram,simulations:n,mean:total/n,p10:quantile(.1),p50:quantile(.5),p90:quantile(.9),encoding:'exact_integer_frequency_v1',coverage:'Exact outcomes from complete shared simulated games including overtime; not chart-bin approximations.'};
}
export function exactGameDistribution(result:Record<string,any>,contract:PropMarketContract):PropDistribution|null{
 if(result.distributionEncoding!=='exact_integer_frequency_v1'&&!(result.distributionEncoding===undefined&&result.engineVersion==='pbp-runtime-4.0.0'))return null;
 const n=result.simulations,home=exactHistogram(result.scoreDistributions?.[result.home],n,0,1000),away=exactHistogram(result.scoreDistributions?.[result.away],n,0,1000),margin=exactHistogram(result.marginDistribution,n,-1000,1000),total=exactHistogram(result.totalDistribution,n,0,2000);
 if(!home||!away||!margin||!total||Math.abs(home.mean!+away.mean!-total.mean!)>1e-8||Math.abs(home.mean!-away.mean!-margin.mean!)>1e-8)return null;
 const target=contract.subject?.teamId??contract.team,team=canonicalPropTeam(target),isHome=team===canonicalPropTeam(result.home),isAway=team===canonicalPropTeam(result.away);
 if(contract.stat==='totalPoints')return total;
 if(!isHome&&!isAway)return null;
 if(contract.stat==='teamTotal')return isHome?home:away;
 if(contract.stat==='spread'||contract.stat==='gameWinner')return isHome?margin:exactHistogram({histogram:margin.histogram.map(r=>({value:-r.value,count:r.count}))},n,-1000,1000);
 return null;
}
export function gameOutcomeHit(value:number,contract:PropMarketContract,side:'YES'|'NO'){
 if(contract.stat==='gameWinner'&&value===0){const tie=new Decimal(contract.settlement.tiePayoutCents??'NaN'),receipt=side==='YES'?tie:new Decimal(100).sub(tie);return receipt.eq(100);}
 const yes=thresholdHit(value,contract.threshold,contract.operator);return side==='YES'?yes:!yes;
}
export function buildGameMarketResearch(input:PropMarketContract,detail:PublicGameDetail|null,side:'YES'|'NO',runId:string,now=new Date()):PropResearch{
 const contract=recheckPropMarketFreshness(input,now),analysis=detail?.analysis,result=analysis?.result??{},reasons:string[]=[];
 if(!detail||detail.game.id!==contract.gameId||Date.parse(detail.game.startTime)!==Date.parse(contract.eventStart))reasons.push('The scheduled game identity and kickoff do not match this exact contract.');
 if(!analysis||analysis.status!=='completed'||analysis.stale)reasons.push('A current completed whole-game simulation is unavailable.');
 if(contract.playerId!==null||contract.mapping.status!=='verified')reasons.push('The exact team/game subject must be verified without a fabricated player identity.');
 if(!contract.settlement.rulesVerified||!contract.settlement.modelCompatible||!contract.settlement.fullGame||!contract.settlement.overtimeIncluded)reasons.push('The exact full-game including overtime settlement rules are unsupported.');
 if(!Number.isFinite(contract.threshold)||!['gt','gte','lt','lte','eq'].includes(contract.operator))reasons.push('The exact threshold and comparison operator are unsupported.');
 if(contract.stat==='gameWinner'&&(contract.threshold!==0||contract.operator!=='gt'||contract.settlement.tiePayoutCents==null||!/^\d+(?:\.\d+)?$/.test(contract.settlement.tiePayoutCents)||!Number.isFinite(Number(contract.settlement.tiePayoutCents))||Number(contract.settlement.tiePayoutCents)>100))reasons.push('Winner contracts require an explicit verified finite tie payout.');
 const game=detail?.game??{id:contract.gameId,startTime:contract.eventStart,season:Number(contract.gameId.slice(0,4)),week:Number(contract.gameId.split('_')[1]),status:'scheduled' as const,home:{id:contract.gameId.split('_')[3],name:contract.gameId.split('_')[3],abbreviation:contract.gameId.split('_')[3]},away:{id:contract.gameId.split('_')[2],name:contract.gameId.split('_')[2],abbreviation:contract.gameId.split('_')[2]},sources:[]};
 if(result.home&&canonicalPropTeam(result.home)!==canonicalPropTeam(game.home.id)||result.away&&canonicalPropTeam(result.away)!==canonicalPropTeam(game.away.id)||result.eventStart&&Date.parse(result.eventStart)!==Date.parse(game.startTime))reasons.push('The simulated home/away axes or event time differ from the actual matchup.');
 const distribution=exactGameDistribution(result,contract);if(!distribution)reasons.push('Reconciled exact score, margin and total frequency distributions are unavailable.');
 let hits=0,p:number|null=null;if(!reasons.length&&distribution){hits=distribution.histogram.filter(r=>gameOutcomeHit(r.value,contract,side)).reduce((sum,r)=>sum+r.count,0);p=hits/distribution.simulations;}
 const n=distribution?.simulations??0,parameter=p===null?null:gameParameterInterval(result,contract,side),condition='Conditional on normal full-game completion including overtime. Discretionary cancellation, forfeit and fair-price exceptions are not modeled.';
 let settlementEstimate:PropResearch['settlementEstimate'];
 if(p!==null&&distribution&&contract.stat==='gameWinner'){
  const win=distribution.histogram.filter(r=>r.value>0).reduce((sum,r)=>sum+r.count,0)/n,loss=distribution.histogram.filter(r=>r.value<0).reduce((sum,r)=>sum+r.count,0)/n,tie=distribution.histogram.filter(r=>r.value===0).reduce((sum,r)=>sum+r.count,0)/n,tiePayout=side==='YES'?new Decimal(contract.settlement.tiePayoutCents!):new Decimal(100).sub(contract.settlement.tiePayoutCents!);
  settlementEstimate={winProbability:side==='YES'?win:loss,lossProbability:side==='YES'?loss:win,tieProbability:tie,tiePayoutCents:tiePayout.toString(),expectedSettlementCents:new Decimal(side==='YES'?win:loss).mul(100).add(tiePayout.mul(tie)).toFixed(6),condition:condition+' Raw probability means the full 100-cent payout; partial tie payments are shown separately.'};
 }
 const checks=[{name:'Exact scheduled game and subject',passed:contract.mapping.status==='verified'&&contract.playerId===null},{name:'Verified full-game including overtime rules',passed:contract.settlement.modelCompatible&&contract.settlement.rulesVerified},{name:'Reconciled exact whole-game distributions',passed:!!distribution},{name:'Current verified simulation inputs',passed:analysis?.status==='completed'&&!analysis.stale},{name:'Current verified quote',passed:contract.verification.current&&contract.verification.quoteVerified},{name:'Published injury/practice coverage',passed:detail?.injuries.status==='available'},{name:'Verified transaction costs',passed:contract.fees.calculationStatus==='verified_explicit'},{name:'Validated calibration for this exact market/model',passed:false}];
 const at=now.toISOString(),affected=(detail?.injuries.items??[]).map(i=>({id:i.id,name:i.player,status:i.status})),id=sha({contract:contract.id,rules:contract.rulesHash,subject:contract.subject,stat:contract.stat,threshold:contract.threshold,operator:contract.operator,side,simulation:analysis?.id??null,input:analysis?.inputHash??null,withheld:reasons});
 return{id,runId,game,contract,player:{id:null,name:contract.playerName,team:contract.team,position:null},side,status:reasons.length?'withheld':contract.verification.current?'conditional':'stale',stale:!!analysis?.stale||!contract.verification.current,withheldReasons:reasons,simulationId:analysis?.id??null,modelVersion:result.modelVersion??null,inputVersion:result.inputDataVersion??analysis?.inputHash??null,simulations:n,probability:{raw:p,calibrated:null,conditional:true,condition,interval95:p===null?null:wilson(hits,n),samplingError:p===null?null:Math.sqrt(p*(1-p)/n),modelInterval95:parameter?.interval95??null,calibrationStatus:'Insufficient prospective, settled evidence for this exact game-contract category and model.',historicalSampleSize:0,historicalBrier:null},valuation:valueProp(contract,side,p),distribution,injury:{status:'Team/game research',message:detail?.injuries.message??'Current verified injury coverage is unavailable.',checkedAt:detail?.injuries.checkedAt??null,affectedPlayers:affected,fullyAdjusted:analysis?.research?.injuryImpact?.fullyAdjusted===true,probabilityChange:null},sensitivity:{injury:'Only statistically supported availability cohorts are applied. Verified reports are evidence, not an arbitrary numerical multiplier.',weather:'Current weather is reported; no unsupported numerical weather coefficient is applied.',injuryDelta:null,weatherDelta:null},dataQuality:{score:Math.round(100*checks.filter(c=>c.passed).length/checks.length),checks,meaning:'Coverage checks passed; this is not probability, confidence, model accuracy or expected value.'},rankingReason:'Full-game probabilities and market disagreement are separate from fee-aware expected value. Unsupported ranking metrics remain unavailable.',capturedAt:at,updatedAt:at,sources:detail?.sources??[],assumptions:[condition,'Monte Carlo intervals measure sampling noise. Parameter bootstrap intervals measure sensitivity, not validated predictive coverage.','Game winner partial-tie payouts are not counted as full Yes/No hits.','No transaction is placed or recorded by this research.'],...settlementEstimate?{settlementEstimate}:{}};
}
