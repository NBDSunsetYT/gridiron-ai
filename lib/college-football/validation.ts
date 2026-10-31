import Decimal from 'decimal.js';
import audit from '../../docs/reports/v8-cfb-historical-audit.json';

/** A retained, non-promoted retrospective pilot. It never populates prospective
 * calibration or selects a production model, regardless of its sample metrics. */
export function collegeHistoricalPilot(){
 const predictions=audit.predictions.filter(row=>row.heldOutGameExcluded===true&&Number.isFinite(row.predictedHomeWinProbability)&&row.predictedHomeWinProbability>0&&row.predictedHomeWinProbability<1&&[0,1].includes(row.actualHomeWin));
 if(!predictions.length||predictions.length!==audit.evaluatedGames)return{status:'unavailable',sampleSize:0,calibrated:false,promoted:false,message:'The retained college model audit could not be verified.'};
 const brier=predictions.reduce((sum,row)=>sum.add(new Decimal(row.predictedHomeWinProbability).sub(row.actualHomeWin).pow(2)),new Decimal(0)).div(predictions.length).toNumber();
 const logLoss=predictions.reduce((sum,row)=>sum-Math.log(row.actualHomeWin?row.predictedHomeWinProbability:1-row.predictedHomeWinProbability),0)/predictions.length;
 return{sport:'CFB',status:'retrospective_not_promoted',sampleSize:predictions.length,brierScore:brier,logLoss,modelVersion:audit.modelVersion,engineVersion:audit.engineVersion,checkedAt:audit.checkedAt,sourceUrl:audit.sourceUrl,sourceSha256:audit.sourceSha256,publicationAvailabilityVerified:false,calibrated:false,promoted:false,marketBenchmark:null,selection:audit.selection,limitations:audit.limitations,message:'Small retrospective pilot with weak results; not promoted. This does not establish prospective calibration, reliable accuracy or market advantage.'};
}
