/** Pure count arithmetic for archived complete-game outcomes. No model execution or market-price inference. */
export class NBAProbabilityError extends Error{constructor(message:string,public status=422){super(message);}}
export function evaluateNBAHistogram(histogram:any[],count:number,threshold:number,side:string){
 if(!Number.isSafeInteger(count)||count<1000||!Number.isFinite(threshold)||!Array.isArray(histogram)||!histogram.length||!['over','under','yes','no'].includes(side.toLowerCase()))throw new NBAProbabilityError('An exact supported NBA threshold and full-game distribution are required.',422);
 let n=0,k=0,push=0;const seen=new Set<number>();
 for(const bin of histogram){if(!Number.isSafeInteger(bin.value)||!Number.isSafeInteger(bin.count)||bin.count<1||seen.has(bin.value))throw new NBAProbabilityError('NBA distribution failed reconciliation.',502);seen.add(bin.value);n+=bin.count;if(['over','under'].includes(side.toLowerCase())&&bin.value===threshold)push+=bin.count;if(side.toLowerCase()==='over'?bin.value>threshold:side.toLowerCase()==='under'?bin.value<threshold:side.toLowerCase()==='yes'?bin.value>=1:bin.value===0)k+=bin.count;}
 if(n!==count)throw new NBAProbabilityError('NBA distribution does not match the complete-game count.',502);const p=k/n,z=1.959963984540054,den=1+z*z/n,center=(p+z*z/(2*n))/den,radius=z*Math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den;
 return{rawProbability:p,successes:k,validGames:n,pushProbability:push/n,calibratedProbability:null,monteCarloSE:Math.sqrt(p*(1-p)/n),monteCarloInterval95:[Math.max(0,center-radius),Math.min(1,center+radius)],method:'Raw complete-game outcomes; no approved NBA calibration artifact.'};
}
