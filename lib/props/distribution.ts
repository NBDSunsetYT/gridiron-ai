import {jStat} from 'jstat';
export function priorTail(base:any,threshold:number,side:'Over'|'Under'){
 let cdf:number;
 if(base?.family==='normal'&&base.scale>0&&[base.location,base.scale].every(Number.isFinite)){const boundary=side==='Under'?Math.ceil(threshold)-.5:Math.floor(threshold)+.5;cdf=jStat.normal.cdf(boundary,base.location,base.scale);
 }else if(base?.family==='student_t'&&base.df>0&&base.scale>0&&[base.location,base.df,base.scale].every(Number.isFinite)){
  const boundary=side==='Under'?Math.ceil(threshold)-.5:Math.floor(threshold)+.5,x=(boundary-base.location)/base.scale;cdf=jStat.studentt.cdf(x,base.df);
 }else{const k=side==='Under'?Math.ceil(threshold)-1:Math.floor(threshold);
  if(k<0)cdf=0;
  else if(base?.family==='negative_binomial'&&base.size>0&&base.probability>0&&base.probability<1)cdf=jStat.ibeta(base.probability,base.size,k+1);
  else if(base?.family==='poisson'&&base.mean>0&&Number.isFinite(base.mean))cdf=jStat.poisson.cdf(k,base.mean);
  else throw Error('Unsupported validated prior distribution');
 }
 if(!Number.isFinite(cdf)||cdf<0||cdf>1+1e-9)throw Error('Prior CDF failed validation');return Math.max(0,Math.min(1,side==='Over'?1-cdf:cdf));
}
type CalibratedCdf={probability:number;interval:[number,number];validation:any;reason:string};
export function calibratedCdf(probability:number,interval:[number,number],artifact:any,side:'Over'|'Under'='Over'):CalibratedCdf|null{
 // Artifacts are fitted to Over tails. An Under is the complement of the
 // corresponding inclusive upper tail, not a second use of the same intercept.
 if(side==='Under'){
  const over=calibratedCdf(1-probability,[1-interval[1],1-interval[0]],artifact,'Over');
  return over?{...over,probability:1-over.probability,interval:[1-over.interval[1],1-over.interval[0]] as [number,number]}:null;
 }
 const c=artifact?.calibrator,v=c?.validation;
 if(!Number.isFinite(probability)||!interval.every(Number.isFinite)||!c||c.method!=='regularized_platt'||v?.chronological!==true||v.testPredictions<100||v.testGames<8||!Number.isFinite(v.familywiseAdjustedPValue)||v.familywiseAdjustedPValue>.025||v.pairedGameBootstrapBrierDifference95?.[1]>=0||v.logLoss>v.rawLogLoss||!Number.isFinite(c.intercept)||!Number.isFinite(c.slope)||c.slope<=0||probability<c.minimumProbability||probability>c.maximumProbability)return null;
 const logit=(p:number)=>Math.log(Math.max(1e-12,Math.min(1-1e-12,p))/(1-Math.max(1e-12,Math.min(1-1e-12,p)))),sigmoid=(x:number)=>1/(1+Math.exp(-x)),apply=(p:number)=>sigmoid(c.intercept+c.slope*logit(p));
 if(!Array.isArray(c.covariance)||c.covariance.length!==2||c.covariance.some((a:any)=>!Array.isArray(a)||a.length!==2||!a.every(Number.isFinite)))return null;
 const radius=(p:number)=>{const x=logit(p);return 2.2414027276*Math.sqrt(Math.max(0,c.covariance[0][0]+2*x*c.covariance[0][1]+x*x*c.covariance[1][1]));};
 return{probability:apply(probability),interval:[sigmoid(c.intercept+c.slope*logit(interval[0])-radius(interval[0])),sigmoid(c.intercept+c.slope*logit(interval[1])+radius(interval[1]))] as [number,number],validation:v,reason:'Earlier-season Platt recalibration passed an independent chronological holdout and familywise publication gate. The conditional interval includes approximate recalibration uncertainty; prospective contract accuracy and structural uncertainty remain unestablished.'};
}
/** A fixed Jeffreys prior is published only after an exact sport/stat/role
 * chronological audit improves on K/N. It is not calibrated market accuracy. */
export function regularizedHistoricalThreshold(distribution:any,threshold:number,side:'Over'|'Under',sport:string,statistic:string){
 const model=distribution?.regularization,v=model?.validation,bins=distribution?.histogram,n=distribution?.sampleSize;
 const prior=model?.priorValidation;
 const blockValidated=(x:any)=>x?.testWeeks>=8&&Number.isFinite(x.weekBlockAdjustedPValue)&&x.weekBlockAdjustedPValue>=0&&x.weekBlockAdjustedPValue<=.025&&Array.isArray(x.pairedWeekBlockBootstrapBrierDifference95)&&x.pairedWeekBlockBootstrapBrierDifference95.length===2&&x.pairedWeekBlockBootstrapBrierDifference95.every(Number.isFinite)&&x.pairedWeekBlockBootstrapBrierDifference95[1]<0;
 if(!blockValidated(v)||!blockValidated(model?.priorValidation))return null;
 if(prior?.chronological!==true||prior.testSeason!==v?.testSeason-1||prior.testPredictions<100||prior.testGames<8||!Number.isFinite(prior.familywiseAdjustedPValue)||prior.familywiseAdjustedPValue>.025||!Array.isArray(prior.pairedGameBootstrapBrierDifference95)||prior.pairedGameBootstrapBrierDifference95.length!==2||!prior.pairedGameBootstrapBrierDifference95.every(Number.isFinite)||prior.pairedGameBootstrapBrierDifference95[1]>=0||!Number.isFinite(prior.logLoss)||!Number.isFinite(prior.benchmarkLogLoss)||prior.logLoss>prior.benchmarkLogLoss)return null;
 if(model?.approved!==true||!Number.isFinite(Date.parse(model.availableAt))||Date.parse(model.availableAt)>Date.now()||model.sport!==sport||model.statistic!==statistic||model.priorAlpha!==.5||model.priorBeta!==.5||model.window!==24||!model.artifactId||v?.chronological!==true||v.testPredictions<100||v.testGames<8||!Number.isFinite(v.familywiseAdjustedPValue)||v.familywiseAdjustedPValue>.025||!Array.isArray(v.pairedGameBootstrapBrierDifference95)||v.pairedGameBootstrapBrierDifference95.length!==2||!v.pairedGameBootstrapBrierDifference95.every(Number.isFinite)||v.pairedGameBootstrapBrierDifference95[1]>=0||!Number.isFinite(v.logLoss)||!Number.isFinite(v.benchmarkLogLoss)||v.logLoss>v.benchmarkLogLoss||!Number.isFinite(threshold)||!Number.isSafeInteger(n)||n<1||n>24||!Array.isArray(bins)||bins.some((b:any)=>!Number.isFinite(b.value)||!Number.isSafeInteger(b.count)||b.count<0)||bins.reduce((s:number,b:any)=>s+b.count,0)!==n)return null;
 const counts=['passingAttempts','completions','interceptions','passingTouchdowns','carries','rushingTouchdowns','targets','receptions','receivingTouchdowns','touchdowns'];
 if(counts.includes(statistic)&&(bins.some((b:any)=>b.value<0||!Number.isInteger(b.value))||side==='Under'&&threshold<=0||side==='Over'&&threshold<0))return null;
 const hits=bins.filter((b:any)=>side==='Over'?b.value>threshold:b.value<threshold).reduce((s:number,b:any)=>s+b.count,0),a=hits+.5,b=n-hits+.5,probability=a/(n+1),interval=[jStat.beta.inv(.025,a,b),jStat.beta.inv(.975,a,b)];
 if(!interval.every(Number.isFinite))return null;
 return{posteriorProbability:probability,estimateProbability:probability,modelProbability:probability,rawProbability:null,empiricalProbability:hits/n,calibratedProbability:null,modelInterval95:interval,historicalHits:hits,historicalSampleSize:n,priorEffectiveSampleSize:1,distributionArtifactId:model.artifactId,modelValidation:v,priorSeasonValidation:prior,method:'regularized_history',methodLabel:'Bayesian historical estimate · uncalibrated',modelVersion:model.version,simulations:null,successfulSimulations:null,monteCarloInterval95:null,monteCarloStandardError:null,expectedValue:null,state:'ready',reasonCode:null,reason:'Jeffreys beta-binomial posterior: (observed hits + 0.5) / (recorded games + 1). The fixed weak prior passed two chronological sport/stat/role validation periods against unsmoothed K/N. This participation-conditioned historical estimate does not fully quantify current injuries, role changes, opponents, weather or structural uncertainty; it is not calibrated contract accuracy.'};
}
/** A conditional Bayesian CDF estimate, never Monte Carlo or calibrated accuracy. */
export function hierarchicalThreshold(distribution:any,threshold:number,side:'Over'|'Under',sport:string,statistic:string){
 const model=distribution.hierarchical,v=model?.validation,bins=distribution.histogram,n=distribution.sampleSize;
 if(!model||model.sport!==sport||model.statistic!==statistic||v?.chronological!==true||v.testPredictions<100||v.testGames<8||!Number.isFinite(v.familywiseAdjustedPValue)||v.familywiseAdjustedPValue>.025||!v.pairedGameBootstrapBrierDifference95?.every(Number.isFinite)||v.pairedGameBootstrapBrierDifference95?.[1]>=0||v.logLoss>v.benchmarkLogLoss||!Array.isArray(v.pairedGameBootstrapBrierDifference95)||!model.artifactId||!Number.isFinite(model.strength)||model.strength<=0||!Number.isSafeInteger(n)||n<1||!Array.isArray(bins)||bins.reduce((sum:number,b:any)=>sum+b.count,0)!==n)return null;
 try{
  const hits=bins.filter((b:any)=>side==='Over'?b.value>threshold:b.value<threshold).reduce((sum:number,b:any)=>sum+b.count,0),q=priorTail(model.base,threshold,side),a=hits+model.strength*q,b=n-hits+model.strength*(1-q),probability=a/(a+b);
  let interval:[number,number]=a===0?[0,0]:b===0?[1,1]:[jStat.beta.inv(.025,a,b),jStat.beta.inv(.975,a,b)];if(interval.some(x=>!Number.isFinite(x)||x<0||x>1)||interval[0]>interval[1])interval=[0,1];
  const rawBand:[number,number]=a===0?[0,0]:b===0?[1,1]:[jStat.beta.inv(.0125,a,b),jStat.beta.inv(.9875,a,b)],calibration=calibratedCdf(probability,rawBand,model,side);
  return{posteriorProbability:probability,estimateProbability:calibration?.probability??probability,modelProbability:probability,rawProbability:null,empiricalProbability:hits/n,calibratedProbability:calibration?.probability??null,calibratedInterval95:calibration?.interval??null,calibrationValidation:calibration?.validation??null,calibrationReason:calibration?.reason??'No approved recalibrator covers this exact predicted probability.',modelInterval95:interval,historicalHits:hits,historicalSampleSize:n,priorEffectiveSampleSize:model.strength,distributionArtifactId:model.artifactId,modelValidation:v,method:'hierarchical_distribution',methodLabel:calibration?'Hierarchical distribution · retrospective recalibration':'Validated hierarchical distribution · uncalibrated',modelVersion:model.version,simulations:null,successfulSimulations:null,monteCarloInterval95:null,monteCarloStandardError:null,expectedValue:null,state:'ready',reasonCode:null,reason:'Partial-pooling distribution validated on chronological held-out player-stat outcomes. The credible interval is conditional on the fitted role-cohort base; opponent, role, injury, weather and structural uncertainty remain incomplete. This is not calibrated contract accuracy or verified after-fee value.'};
 }catch{return null;}
}
