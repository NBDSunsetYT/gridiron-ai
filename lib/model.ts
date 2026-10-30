/** Transparent empirical baseline. This is not a trained NFL forecasting model. */
export const MODEL_VERSION = 'empirical-distribution-1.0';
export function decimalOdds(american: number): number {
  if (!Number.isFinite(american) || Math.abs(american) < 100 || Math.abs(american) > 100000) throw new Error('American odds must be at least +100 or at most -100.');
  return american > 0 ? 1 + american / 100 : 1 + 100 / -american;
}
export function americanOdds(decimal: number): number | null {
  if (!Number.isFinite(decimal) || decimal <= 1) return null;
  return decimal >= 2 ? Math.round((decimal - 1) * 100) : Math.round(-100 / (decimal - 1));
}
export function wilson(successes: number, n: number): [number, number] {
  if (n <= 0) return [0, 1];
  const z = 1.95996398454, p = successes / n, d = 1 + z * z / n;
  const c = (p + z * z / (2 * n)) / d;
  const r = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d;
  return [Math.max(0, c - r), Math.min(1, c + r)];
}
function checkSamples(samples: number[]) {
  if (!Array.isArray(samples) || samples.length < 20 || samples.length > 10000 || samples.some(x => !Number.isFinite(x))) throw new Error('Provide 20–10,000 finite observations in chronological order.');
}
export function distribution(samples: number[], threshold: number, direction: 'over' | 'under', odds: number) {
  checkSamples(samples);
  if (!Number.isFinite(threshold) || !['over','under'].includes(direction)) throw new Error('A finite threshold and over/under direction are required.');
  const dec = decimalOdds(odds), n = samples.length;
  const wins = samples.filter(x => direction === 'over' ? x > threshold : x < threshold).length;
  const pushes = samples.filter(x => x === threshold).length;
  const resolved = n - pushes;
  if (resolved < 20) throw new Error('At least 20 non-push observations are required.');
  // Jeffreys posterior mean avoids certainty at the boundary. Push frequency stays empirical.
  const probability = (wins + .5) / (resolved + 1), pushProbability = pushes / n;
  const mean = samples.reduce((a,b)=>a+b,0) / n;
  const sd = Math.sqrt(samples.reduce((a,b)=>a+(b-mean)**2,0)/(n-1));
  const min = Math.min(...samples), max = Math.max(...samples), width = (max - min) / 10 || 1;
  const histogram = Array.from({length:10},(_,i)=>({value: +(min+width*(i+.5)).toFixed(2),count:0}));
  for (const x of samples) histogram[Math.min(9,Math.floor((x-min)/width))].count++;
  return {
    probability, hitProbability: probability, pushProbability, fairOdds:americanOdds(1/probability),
    breakEven:1/dec, expectedValue:(1-pushProbability)*(probability*(dec-1)-(1-probability)),
    uncertainty:wilson(wins,resolved), sampleSize:n, resolvedSampleSize:resolved,
    projection:{mean,sd}, histogram, modelVersion:MODEL_VERSION,
    metrics: rollingMetrics(samples,threshold,direction),
    limitations:['Unadjusted empirical baseline; opponent, injuries, role changes and weather are not modeled.','Observations must be comparable and ordered oldest to newest. The interval describes sampling uncertainty, not all model risk.','Retrospective hit frequency does not establish future edge.'],
  };
}
export function rollingMetrics(samples:number[],threshold:number,direction:'over'|'under') {
  // One-step rolling-origin validation. Each prediction sees only strictly earlier outcomes.
  const rows:{p:number;y:number}[]=[];
  for(let i=20;i<samples.length;i++) {
    if(samples[i]===threshold) continue;
    const past=samples.slice(0,i).filter(x=>x!==threshold);
    if(past.length<20) continue;
    const hits=past.filter(x=>direction==='over'?x>threshold:x<threshold).length;
    rows.push({p:(hits+.5)/(past.length+1),y:+(direction==='over'?samples[i]>threshold:samples[i]<threshold)});
  }
  if(rows.length<20) return null;
  const calibration=Array.from({length:10},(_,i)=>{
    const bucket=rows.filter(r=>Math.min(9,Math.floor(r.p*10))===i);
    return {bucket:`${i*10}–${(i+1)*10}%`,n:bucket.length,predicted:bucket.length?bucket.reduce((s,r)=>s+r.p,0)/bucket.length:null,observed:bucket.length?bucket.reduce((s,r)=>s+r.y,0)/bucket.length:null,interval:bucket.length?wilson(bucket.reduce((s,r)=>s+r.y,0),bucket.length):null};
  });
  return {n:rows.length,brier:rows.reduce((s,r)=>s+(r.p-r.y)**2,0)/rows.length,logLoss:-rows.reduce((s,r)=>s+r.y*Math.log(r.p)+(1-r.y)*Math.log(1-r.p),0)/rows.length,accuracy:rows.filter(r=>+(r.p>=.5)===r.y).length/rows.length,calibration,validation:'rolling-origin; first 20 outcomes reserved for initial fit',scope:'User-supplied observations only; not independently verified NFL performance'};
}
export function parlay(input:{probabilities:number[];odds:number[];independenceAssumed?:boolean;jointSamples?:boolean[][]}) {
  const {probabilities,odds,jointSamples}=input, n=probabilities?.length;
  if(!n||n<2||n>12||odds?.length!==n||probabilities.some(p=>!Number.isFinite(p)||p<=0||p>=1)) throw new Error('Select 2–12 legs with probabilities strictly between 0 and 1 and valid odds.');
  const independenceProbability=probabilities.reduce((a,b)=>a*b,1),decimalPayout=odds.map(decimalOdds).reduce((a,b)=>a*b,1);
  let jointProbability:number,uncertainty:[number,number]|null=null,method:string;
  if(jointSamples) {
    if(jointSamples.length<20||jointSamples.length>10000||jointSamples.some(r=>r.length!==n||r.some(v=>typeof v!=='boolean'))) throw new Error('Provide 20–10,000 aligned outcome rows, one boolean per leg.');
    const wins=jointSamples.filter(r=>r.every(Boolean)).length;
    jointProbability=(wins+.5)/(jointSamples.length+1);uncertainty=wilson(wins,jointSamples.length);method='Joint empirical outcomes; dependence is preserved in aligned scenarios.';
  } else {
    if(!input.independenceAssumed) throw new Error('Joint outcomes are required when dependence is unknown. Explicitly opt into an independence-only scenario to compare it.');
    jointProbability=independenceProbability;method='Hypothetical independence assumption; does not account for material correlations.';
  }
  return {jointProbability,independenceProbability,decimalPayout,expectedValue:jointProbability*decimalPayout-1,uncertainty,method,variance:decimalPayout**2*jointProbability*(1-jointProbability),sampleSize:jointSamples?.length??0,warning:'Combined sportsbook pricing, push/void rules and availability must be verified. Independence is not an estimate for correlated legs.'};
}
