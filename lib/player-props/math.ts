import Decimal from 'decimal.js';
import {wilson} from '../model';
import type {PublicGameDetail} from '../public-nfl/types';
import {sha} from '../public-nfl/sources';
import {propParameterInterval,decodePropParameterSamples} from './bootstrap';
import {recheckPropMarketFreshness} from './normalize';
import type {PropMarketContract} from './market-types';
import {isGameMarket} from './market-types';
import {buildGameMarketResearch} from './game-math';
import type {PropResearch,PropDistribution} from './types';

export function thresholdHit(value:number,threshold:number,operator:string){
 switch(operator){case'gt':return value>threshold;case'gte':return value>=threshold;case'lt':return value<threshold;case'lte':return value<=threshold;case'eq':return value===threshold;default:throw Error('Unsupported exact threshold comparison.');}
}
export function exactPropDistribution(result:Record<string,any>,playerId:string,stat:string):PropDistribution|null{
 const distribution=result.players?.[playerId]?.[stat],n=result.simulations;
 if(!Number.isInteger(n)||n<10000||n>100000||!Array.isArray(distribution?.histogram))return null;
 const seen=new Set<number>();let count=0,total=0;
 for(const row of distribution.histogram){if(!row||typeof row!=='object'||!Number.isInteger(row.value)||!Number.isInteger(row.count)||row.count<0||seen.has(row.value))return null;seen.add(row.value);count+=row.count;total+=row.value*row.count;}
 if(count!==n)return null;
 // Previous complete-game releases also used exact integer Counter frequencies.
 // A future chart-binned encoding must never be interpreted as exact outcomes.
 if(result.distributionEncoding!=='exact_integer_frequency_v1'&&!(result.distributionEncoding===undefined&&result.engineVersion==='pbp-runtime-4.0.0'))return null;
 const histogram=[...distribution.histogram].sort((a,b)=>a.value-b.value);
 const quantile=(q:number)=>{let c=0;for(const row of histogram){c+=row.count;if(c>=Math.ceil(n*q))return row.value;}return null;};
 return{histogram,simulations:n,mean:total/n,p10:quantile(.1),p50:quantile(.5),p90:quantile(.9),encoding:'exact_integer_frequency_v1',coverage:stat==='touchdowns'?'Offensive rushing and receiving touchdowns only; return/defensive touchdowns are not modeled.':'Full simulated game including modeled overtime.'};
}
export function valueProp(contract:PropMarketContract,side:'YES'|'NO',probability:number|null):PropResearch['valuation']{
 const ask=side==='YES'?contract.yesAskCents:contract.noAskCents;
 const base={breakEven:null,fairCents:null,netValueCents:null,entryCostCents:null,feesVerified:contract.fees.calculationStatus==='verified_explicit'&&contract.fees.entryFeeCents!==null&&contract.fees.winFeeCents!==null&&contract.fees.rounding!==null,reason:''} as PropResearch['valuation'];
 if(!contract.verification.current||!contract.verification.quoteVerified||ask===null)return{...base,reason:'A verified fresh ask is unavailable. No executable fill is assumed.'};
 if(!contract.settlement.unconditionalValuationSupported)return{...base,reason:'Probability is conditional on participation and normal completion. Exceptional/non-participation settlement is not modeled, so unconditional fair value and net value are withheld.'};
 if(probability===null||!Number.isFinite(probability)||probability<0||probability>1)return{...base,reason:'No supported model probability is available.'};
 const fairCents=new Decimal(probability).mul(100).toFixed(6);
 const fees=contract.fees;
 if(fees.calculationStatus!=='verified_explicit'||fees.entryFeeCents===null||fees.winFeeCents===null||fees.rounding===null)return{...base,fairCents,reason:'Transaction fees and rounding for this contract/account are unverified; cost-adjusted break-even and net value are withheld.'};
 let price:Decimal,fee:Decimal,win:Decimal;try{price=new Decimal(ask);fee=new Decimal(fees.entryFeeCents);win=new Decimal(fees.winFeeCents);}catch{return{...base,reason:'Price or fee terms are invalid.'};}
 if(!price.isFinite()||!fee.isFinite()||!win.isFinite())return{...base,reason:'Price or fee terms are invalid.'};
 if(price.lte(0)||price.gte(100)||fee.lt(0)||win.lt(0)||win.gte(100))return{...base,reason:'Price or fee terms are invalid.'};
 const cost=fees.rounding==='collateral_total_up_to_cent'?price.add(fee).ceil():price.add(fees.rounding==='up_to_cent'?fee.ceil():fee),receipt=new Decimal(100).sub(fees.rounding==='up_to_cent'?win.ceil():win);
 return{breakEven:cost.div(receipt).toNumber(),fairCents,netValueCents:receipt.mul(probability).sub(cost).toFixed(8),entryCostCents:cost.toFixed(),feesVerified:true,reason:'One 100-cent binary contract valued at the observed ask using the explicitly verified per-contract entry/win fees. Available fills and liquidity are not guaranteed.'};
}
export function buildPropResearch(contractInput:PropMarketContract,detail:PublicGameDetail|null,side:'YES'|'NO',runId:string,now=new Date()):PropResearch{
 if(isGameMarket(contractInput.stat))return buildGameMarketResearch(contractInput,detail,side,runId,now);
 const contract=recheckPropMarketFreshness(contractInput,now),analysis=detail?.analysis,result=analysis?.result??{},playerId=contract.playerId;
 const reasons:string[]=[];
 if(!Number.isFinite(contract.threshold)||!['gt','gte','lt','lte','eq'].includes(contract.operator))reasons.push('The exact finite threshold and comparison operator are unsupported.');
 if(!contract.settlement.fullGame||!contract.settlement.overtimeIncluded)reasons.push('The model requires full-game rules including overtime.');
 if(playerId&&result.publicPlayerForecastsWithheld?.[playerId])reasons.push(String(result.publicPlayerForecastsWithheld[playerId]));
 if(contract.mapping.status!=='verified'||!playerId)reasons.push(contract.mapping.reason||'The exact current NFL player identity is not verified.');
 if(!contract.settlement.rulesVerified||!contract.settlement.modelCompatible)reasons.push(contract.settlement.reason||'Settlement/statistical coverage is incompatible with the current model.');
 if(!analysis||analysis.status!=='completed')reasons.push(analysis?.error||'A completed complete-game simulation is not available yet.');
 if(analysis?.stale)reasons.push('Verified game inputs changed; this simulation is stale.');
 if(detail&&detail.game.id!==contract.gameId)reasons.push('Contract and simulation game identities do not match.');
 const distribution=playerId?exactPropDistribution(result,playerId,contract.stat):null;
 if(!distribution)reasons.push('An exact current-player outcome distribution is unavailable. Missing outcomes are not zero.');
 if(contract.stat==='touchdowns'&&/return|defens|special.team/i.test(contract.settlement.statCoverage))reasons.push('This touchdown rule includes outcomes outside the offensive rushing/receiving model.');
 let p:number|null=null,hits=0;
 if(!reasons.length&&distribution){hits=distribution.histogram.filter(row=>thresholdHit(row.value,contract.threshold,contract.operator)).reduce((n,row)=>n+row.count,0);if(side==='NO')hits=distribution.simulations-hits;p=hits/distribution.simulations;}
 const n=distribution?.simulations??0;
 const parameter=p===null||!playerId?null:propParameterInterval(result,playerId,contract.stat,contract.threshold,contract.operator,side.toLowerCase() as 'yes'|'no');
 const affected=(detail?.injuries.items??[]).filter(row=>row.id===playerId||row.team===contract.team||row.team===contract.opponent).map(row=>({id:row.id,name:row.player,status:row.status}));
 const self=affected.find(row=>row.id===playerId);
 const coverageChecks=[{name:'Exact player mapping',passed:contract.mapping.status==='verified'},{name:'Current verified quote',passed:contract.verification.current&&contract.verification.quoteVerified},{name:'Compatible verified statistic rules',passed:contract.settlement.modelCompatible&&contract.settlement.rulesVerified},{name:'Exact complete-game distribution',passed:!!distribution},{name:'Fresh game simulation',passed:analysis?.status==='completed'&&!analysis.stale},{name:'Published injury/practice coverage',passed:detail?.injuries.status==='available'},{name:'Verified transaction costs',passed:contract.fees.calculationStatus==='verified_explicit'},{name:'Validated calibration for this model/category',passed:false}];
 const conditional=!contract.settlement.unconditionalValuationSupported;
 const created=now.toISOString(),game=detail?.game??{id:contract.gameId,startTime:contract.eventStart,season:Number(contract.gameId.slice(0,4)),week:Number(contract.gameId.split('_')[1]),status:'scheduled' as const,home:{id:contract.gameId.split('_')[3],name:contract.gameId.split('_')[3],abbreviation:contract.gameId.split('_')[3]},away:{id:contract.gameId.split('_')[2],name:contract.gameId.split('_')[2],abbreviation:contract.gameId.split('_')[2]},sources:[]};
 const id=sha({contract:contract.id,rules:contract.rulesHash,playerId,stat:contract.stat,threshold:contract.threshold,operator:contract.operator,side,simulation:analysis?.id??null,input:analysis?.inputHash??null,withheld:reasons});
 const valuation=valueProp(contract,side,p);
 return{id,runId,game,contract,player:{id:playerId,name:contract.playerName,team:contract.team,position:contract.position},side,status:reasons.length?'withheld':!contract.verification.current?'stale':conditional?'conditional':'available',stale:!!analysis?.stale||!contract.verification.current,withheldReasons:reasons,simulationId:analysis?.id??null,modelVersion:result.modelVersion??null,inputVersion:result.inputDataVersion??analysis?.inputHash??null,simulations:n,
 probability:{raw:p,calibrated:null,conditional,condition:conditional?'Historical-usage baseline assuming player participation and normal completion. Availability mixtures, non-participation and exceptional payouts are not jointly modeled.':null,interval95:p===null?null:wilson(hits,n),samplingError:p===null?null:Math.sqrt(p*(1-p)/n),modelInterval95:parameter?.interval95??null,calibrationStatus:'Insufficient prospectively settled evidence for this exact model and prop category.',historicalSampleSize:0,historicalBrier:null},valuation,distribution,
 injury:{status:self?.status??'No individual designation verified',message:detail?.injuries.message??'Current injury coverage unavailable.',checkedAt:detail?.injuries.checkedAt??null,affectedPlayers:affected,fullyAdjusted:detail?.analysis?.research?.injuryImpact?.fullyAdjusted===true,probabilityChange:null},
 sensitivity:{injury:'Only evidence-supported availability cohorts are applied. A new report is not proof of a causal probability change.',weather:'Available forecasts are reported; numerical weather adjustments are not fitted.',injuryDelta:null,weatherDelta:null},dataQuality:{score:Math.round(100*coverageChecks.filter(check=>check.passed).length/coverageChecks.length),checks:coverageChecks,meaning:'Percentage of explicit coverage checks passed; this is not hit probability, confidence, calibration or expected value.'},rankingReason:valuation.netValueCents!==null?'Cost-adjusted net value can be compared only under the verified complete settlement terms.':'Ranked by verified research coverage and sampling precision. High hit probability alone does not establish positive expected value.',capturedAt:created,updatedAt:created,sources:detail?.sources??[],assumptions:['Research-only historical complete-game baseline; current-player availability conditioning is incomplete.','Monte Carlo intervals measure simulation noise; parameter intervals are bootstrap sensitivity, not validated predictive coverage.','No wager or contract order is placed or recorded by this analysis.']};
}
export function rankPropResearch(rows:PropResearch[]){return [...rows].sort((a,b)=>{const ae=a.valuation.netValueCents,be=b.valuation.netValueCents;if(ae!==null&&be!==null)return new Decimal(be).cmp(ae);if(ae!==null||be!==null)return ae!==null?-1:1;return Number(b.probability.raw!==null)-Number(a.probability.raw!==null)||b.dataQuality.score-a.dataQuality.score||(a.probability.interval95?a.probability.interval95[1]-a.probability.interval95[0]:2)-(b.probability.interval95?b.probability.interval95[1]-b.probability.interval95[0]:2)||a.id.localeCompare(b.id);});}
