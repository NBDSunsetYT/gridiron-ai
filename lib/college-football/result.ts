import {ApiError} from '../auth';
import type {CollegeGame} from './types';

/** Fail closed before a backend result can become a displayed/persisted forecast. */
export function validateCollegeGameResult(value:any,game:CollegeGame,count:number){
 const failed=()=>{throw new ApiError('The college-football game output could not be reconciled. Its probabilities were withheld.',502);};
 if(value?.sport!=='CFB'||value.simulations!==count||value.home!==game.home.id||value.away!==game.away.id||typeof value.modelVersion!=='string'||!value.modelVersion.startsWith('cfb-')||typeof value.engineVersion!=='string'||!value.engineVersion.startsWith('cfb-')||Date.parse(value.eventStart)!==Date.parse(game.startTime))failed();
 const histogram=(v:any,nonnegative=false)=>{if(!Array.isArray(v?.histogram)||!v.histogram.length||v.histogram.length>100001)failed();let n=0;for(const row of v.histogram){if(!Number.isSafeInteger(row.value)||nonnegative&&row.value<0||!Number.isSafeInteger(row.count)||row.count<1)failed();n+=row.count;}if(n!==count)failed();return v.histogram as Array<{value:number;count:number}>;};
 for(const team of [game.home.id,game.away.id])histogram(value.scoreDistributions?.[team],true);
 histogram(value.totalDistribution,true);const margins=histogram(value.marginDistribution),probabilities=[value.homeWinProbability,value.awayWinProbability,value.tieProbability];if(probabilities.some(p=>typeof p!=='number'||!Number.isFinite(p)||p<0||p>1)||Math.abs(probabilities.reduce((a,b)=>a+b,0)-1)>1e-10)failed();
 const expected=[margins.filter(r=>r.value>0),margins.filter(r=>r.value<0),margins.filter(r=>r.value===0)].map(rows=>rows.reduce((sum,row)=>sum+row.count,0)/count);
 if(expected.some((p,index)=>Math.abs(p-probabilities[index])>1e-10)||value.calibratedProbability!==null&&value.calibratedProbability!==undefined)failed();
 if(!value.players||typeof value.players!=='object'||Array.isArray(value.players))failed();
 for(const [id,player] of Object.entries(value.players)){if(!/^cfb:espn:\d{1,12}$/.test(id)||!player||typeof player!=='object')failed();for(const stat of Object.values(player as Record<string,unknown>))histogram(stat);}
 return value as Record<string,any>;
}
