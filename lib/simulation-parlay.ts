import Decimal from 'decimal.js';
import {decimalOdds,wilson} from './model';
/** Evaluate selections against the same generated games, retaining observed joint dependence. */
export function simulationParlay(result:Record<string,any>,contractIds:string[],offer?:{odds:number;source:string;quotedAt:string;sportsbook:string}){
 if(!Array.isArray(contractIds)||contractIds.length<2||contractIds.length>12||new Set(contractIds).size!==contractIds.length)throw Error('Choose 2–12 distinct simulated contract definitions.');
 const contracts=result.contracts;if(!Array.isArray(contracts)||!Array.isArray(result.jointOutcomes)||!result.jointOutcomes.length)throw Error('Insufficient evidence: this run has no joint contract outcomes.');
 const indexes=contractIds.map(id=>{const i=contracts.findIndex((c:any)=>c.id===id);if(i<0)throw Error('A selected contract was not evaluated in this simulation.');return i;});
 const rows=result.jointOutcomes as {outcomes:string[];count:number}[];
 if(rows.some(r=>!Array.isArray(r.outcomes)||r.outcomes.length!==contracts.length||!Number.isFinite(r.count)||r.count<0||r.outcomes.some(v=>!['yes','no','push'].includes(v))))throw Error('The stored joint outcome distribution is invalid.');
 const total=rows.reduce((n,r)=>n+r.count,0);if(total<=0||Math.abs(total-Number(result.simulations))>Math.max(1e-6,total*1e-8))throw Error('Joint outcome counts do not reconcile with the simulation run.');
 const hits=rows.filter(r=>indexes.every(i=>r.outcomes[i]==='yes')).reduce((n,r)=>n+r.count,0);
 const pushes=rows.filter(r=>indexes.some(i=>r.outcomes[i]==='push')).reduce((n,r)=>n+r.count,0);
 const jointProbability=hits/total,pushProbability=pushes/total,independenceProbability=indexes.reduce((p,i)=>p*contracts[i].probability,1);
 const weighted=rows.some(r=>!Number.isInteger(r.count))||Boolean(result.scenarioMixture||result.scenarioWeights||result.availabilityMixture||result.injuryMixture)||/mixture|stratif/i.test(JSON.stringify(result.uncertainty?.method||result.uncertainty?.monteCarlo||''));
 let decimalPayout:number|null=null,expectedValue:number|null=null;
 if(offer){decimalPayout=decimalOdds(offer.odds);if(pushes===0)expectedValue=new Decimal(jointProbability).mul(decimalPayout).sub(1).toNumber();}
 return {contractIds,simulations:total,jointProbability,independenceProbability,dependenceDifference:jointProbability-independenceProbability,pushProbability,monteCarloInterval95:weighted?null:wilson(hits,total),uncertaintyMethod:weighted?'Weighted scenario outcomes; a pooled binomial Monte Carlo interval is not valid. Model uncertainty remains unavailable.':'Wilson interval describes finite-run Monte Carlo noise conditional on this fitted model. Model uncertainty remains unavailable.',offer:offer??null,decimalPayout,expectedValue,method:'Selected legs evaluated against aligned outcomes from the same generated football games.',warning:pushes>0?'Push outcomes occur. Expected value is unavailable until the sportsbook’s exact push, void, and repricing rules are modeled.':offer?'The user-verified combined quote is used for EV; actual execution and available liquidity remain unverified.':'Supply a verified combined parlay quote to evaluate payout and expected value. Individual leg prices are not multiplied into an assumed offered quote.'};
}
