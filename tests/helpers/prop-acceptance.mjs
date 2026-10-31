/** Shared assertions for real production player-prop evidence. Synthetic
 * fixtures are permitted only when the caller explicitly opts into local QA. */
import assert from 'node:assert/strict';
import {assertNoPrivateResearchFields} from './public-acceptance.mjs';
const operators=new Set(['gt','gte','lt','lte','eq']);
const hit=(value,operator,threshold)=>operator==='gt'?value>threshold:operator==='gte'?value>=threshold:operator==='lt'?value<threshold:operator==='lte'?value<=threshold:value===threshold;
export function assertPlayerPropResearch(row,{synthetic=false,requireDistribution=true}={}){
 assertNoPrivateResearchFields(row);
 assert.ok(row&&typeof row==='object'&&typeof row.id==='string'&&row.id.length>0);
 const contract=row.contract,current=row.currentContract??contract;assert.ok(contract&&['DraftKings Predictions','Kalshi'].includes(contract.provider));
 assert.ok(typeof contract.contractId==='string'&&contract.contractId.length>0);assert.ok(typeof contract.eventId==='string'&&contract.eventId.length>0);
 assert.ok(operators.has(contract.operator)&&Number.isFinite(contract.threshold));assert.ok(['YES','NO'].includes(row.side));
 assert.equal(row.game.id,contract.gameId);assert.equal(Date.parse(row.game.startTime),Date.parse(contract.eventStart));
 if(!synthetic){assert.doesNotMatch(JSON.stringify(row),/\bSYNTHETIC\b|\bDEMO\b/i);assert.ok(['authorized_feed','public_exchange'].includes(contract.sourceKind));}
 if(contract.provider==='Kalshi')assert.equal(contract.draftKingsEquivalent,false,'An alternative exchange must not be presented as a verified DraftKings equivalent.');
 assert.ok(typeof contract.rules==='string'&&contract.rules.length>0);assert.ok(typeof contract.rulesHash==='string'&&contract.rulesHash.length>0);assert.ok(/^https:\/\//.test(contract.sourceUrl));
 assert.ok(Array.isArray(row.sources)&&row.sources.length>0);assert.ok(Number.isFinite(Date.parse(row.capturedAt)));assert.ok(typeof row.stale==='boolean');
 if(['available','conditional'].includes(row.status)){
  assert.equal(row.stale,false);assert.equal(contract.mapping.status,'verified');assert.ok(contract.playerId);assert.equal(row.player.id,contract.playerId);assert.equal(row.player.team,contract.team);
  assert.ok([row.game.home.id,row.game.away.id].includes(contract.team));assert.ok([row.game.home.id,row.game.away.id].includes(contract.opponent));assert.notEqual(contract.team,contract.opponent);
  assert.equal(current.verification.current,true);assert.equal(current.verification.quoteVerified,true);assert.equal(current.contractId,contract.contractId);assert.equal(current.threshold,contract.threshold);assert.equal(current.operator,contract.operator);assert.equal(current.rulesHash,contract.rulesHash);assert.ok(Number.isFinite(Date.parse(current.observedAt)));assert.ok(Date.parse(current.observedAt)<=Date.now()+60000);assert.ok(Date.now()-Date.parse(current.observedAt)<15*60000,'Current quotes must have a recent verified collection time.');
 }
 const probability=row.probability;assert.ok(probability&&typeof probability.calibrationStatus==='string');
 for(const key of ['raw','calibrated'])if(probability[key]!==null)assert.ok(Number.isFinite(probability[key])&&probability[key]>=0&&probability[key]<=1);
 if(probability.calibrated!==null){assert.ok(probability.historicalSampleSize>0);assert.ok(probability.calibrationStatus!=='insufficient_evidence');}
 if(probability.raw!==null){
  assert.ok(Number.isInteger(row.simulations)&&row.simulations>=10000&&row.simulations<=100000);
  const distribution=row.distribution;if(requireDistribution||distribution){assert.ok(distribution);assert.equal(distribution.encoding,'exact_integer_frequency_v1');assert.equal(distribution.simulations,row.simulations);
  const histogram=distribution.histogram;assert.ok(Array.isArray(histogram)&&histogram.length>0);const seen=new Set();let total=0,wins=0;
  for(const bucket of histogram){assert.ok(Number.isInteger(bucket.value));assert.ok(Number.isInteger(bucket.count)&&bucket.count>0);assert.ok(!seen.has(bucket.value));seen.add(bucket.value);total+=bucket.count;if(hit(bucket.value,contract.operator,contract.threshold))wins+=bucket.count;}
  assert.equal(total,row.simulations);const expected=(row.side==='YES'?wins:total-wins)/total;
  assert.ok(Math.abs(expected-probability.raw)<1e-10,'Raw exact-threshold probability must reconcile the complete-game outcome frequencies.');}
  assert.ok(Array.isArray(probability.interval95)&&probability.interval95.length===2);assert.ok(probability.interval95[0]<=probability.raw&&probability.interval95[1]>=probability.raw);
  assert.ok(Number.isFinite(probability.samplingError)&&probability.samplingError>=0);assert.ok(Math.abs(probability.samplingError-Math.sqrt(probability.raw*(1-probability.raw)/row.simulations))<1e-6);
 }
 const valuation=row.currentValuation??row.valuation;if(valuation.netValueCents!==null){assert.equal(valuation.feesVerified,true);assert.equal(current.settlement.unconditionalValuationSupported,true);assert.equal(row.stale,false);}
 assert.ok(Number.isFinite(row.dataQuality.score)&&row.dataQuality.score>=0&&row.dataQuality.score<=100);assert.ok(Array.isArray(row.dataQuality.checks));
 return{researchId:row.id,contractId:contract.contractId,provider:contract.provider,playerId:contract.playerId,stat:contract.stat,threshold:contract.threshold,side:row.side,status:row.status,simulations:row.simulations,rawAvailable:probability.raw!==null,calibratedAvailable:probability.calibrated!==null};
}
export function assertPlayerPropScan(scan,{synthetic=false}={}){
 assertNoPrivateResearchFields(scan);assert.ok(Array.isArray(scan.results));assert.ok(Array.isArray(scan.providers));assert.ok(Array.isArray(scan.games));
 const rows=scan.results.map(row=>assertPlayerPropResearch(row,{synthetic,requireDistribution:false}));
 const draftKings=scan.providers.find(provider=>/draftkings/i.test(provider.provider));assert.ok(draftKings,'Primary DraftKings provider availability must be explicit.');
 assert.ok(['available','partial','unavailable'].includes(draftKings.status));assert.ok(typeof draftKings.message==='string'&&draftKings.message.length>0);
 if(draftKings.status==='unavailable')assert.equal(rows.filter(row=>row.provider==='DraftKings Predictions').length,0);
 return{results:rows.length,rawEstimates:rows.filter(row=>row.rawAvailable).length,calibratedEstimates:rows.filter(row=>row.calibratedAvailable).length,providers:scan.providers.map(value=>({provider:value.provider,status:value.status,contracts:value.contracts})),rows};
}
