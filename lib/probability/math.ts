import {wilson} from '../model';
export type Bin={value:number;count:number};
export function thresholdProbability(histogram:Bin[],simulations:number,threshold:number,direction:'over'|'under'|'positive'|'negative'){
 if(![10000,50000,100000].includes(simulations)||!Number.isFinite(threshold)||!Array.isArray(histogram)||!histogram.length||histogram.some(b=>!Number.isFinite(b.value)||!Number.isSafeInteger(b.count)||b.count<0)||histogram.reduce((n,b)=>n+b.count,0)!==simulations)throw Error('The full-game histogram does not reconcile.');
 const hits=histogram.filter(b=>direction==='over'||direction==='positive'?b.value>threshold:b.value<threshold).reduce((n,b)=>n+b.count,0),pushes=histogram.filter(b=>b.value===threshold).reduce((n,b)=>n+b.count,0),p=hits/simulations;
 return{hits,simulations,rawProbability:p,pushes,pushProbability:pushes/simulations,monteCarloSE:Math.sqrt(p*(1-p)/simulations),monteCarloInterval95:wilson(hits,simulations)};
}
export function approvedCalibration(raw:number,artifact:any,expected:{sport:string;market:string;modelVersion:string;kickoff:string}){
 const v=artifact?.validation;
 if(!Number.isFinite(Date.parse(expected.kickoff))||!artifact||artifact.status!=='approved'||artifact.sport!==expected.sport||artifact.market!==expected.market||artifact.modelVersion!==expected.modelVersion||!v?.chronological||!Number.isSafeInteger(v.n)||v.n<200||!Array.isArray(v.brierImprovementCI95)||v.brierImprovementCI95.length!==2||!v.brierImprovementCI95.every(Number.isFinite)||v.brierImprovementCI95[1]>=0||!Number.isFinite(Date.parse(artifact.trainingCutoff))||Date.parse(artifact.trainingCutoff)>=Date.parse(expected.kickoff)||!Number.isFinite(artifact.slope)||!Number.isFinite(artifact.intercept)||!Number.isFinite(raw)||raw<0||raw>1)return null;
 const p=Math.max(1e-9,Math.min(1-1e-9,raw)),z=artifact.intercept+artifact.slope*Math.log(p/(1-p));return z>=0?1/(1+Math.exp(-z)):Math.exp(z)/(1+Math.exp(z));
}
/** Prices deliberately do not belong to the independent model's evidence key. */
export function evidenceIdentity(value:{sport:string;gameId:string;inputVersion:string;modelVersion:string;simulations:number;assumptions:unknown}){return JSON.stringify([value.sport,value.gameId,value.inputVersion,value.modelVersion,value.simulations,value.assumptions]);}
