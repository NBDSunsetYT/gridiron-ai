import {readProbabilitySimulation,saveProbabilitySimulation} from './simulation-storage';
import {createHash,randomUUID} from 'node:crypto';
import {getCache} from '@vercel/functions';
import {footballWrite} from '../college-football/store';
import {simulationParlay} from '../simulation-parlay';
import {ApiError} from '../auth';
import {assertComputeAllowed} from '../compute/policy';
const cache=new Map<string,{until:number;value:any}>();
/** All selected targets are evaluated on the same complete games. Prices never choose the seed or model inputs. */
export async function alignedJoint(sport:'NFL'|'CFB',legs:any[],count:number){
 if(legs.some(l=>l.status!=='ready'||!l.definition)||new Set(legs.map(l=>l.gameId)).size!==1)throw new ApiError('Joint evidence requires supported selections from one verified matchup. Cross-game dependence is not fitted; no marginal probabilities were multiplied.',422);
 const gameId=legs[0].gameId,contracts=legs.map((l,i)=>({...l.definition,id:'leg-'+i}));let payload:any,sourceHash:string,path:string;
 if(sport==='CFB'){const c=await import('../college-football/service'),d=await c.collegeGameDetail(gameId),p=await c.prepareCollegeGame(d.game,count);if(!p.ready||!p.inputHash)throw new ApiError(p.reason,422);sourceHash=p.inputHash;payload={game:c.gamePayload(d.game),simulations:count,seed:2026,contracts};path='cfb/public/targets';}
 else{const c=await import('../public-nfl/service'),p=await c.verifiedProbabilityInputs(gameId,count);sourceHash=p.inputHash;if(legs.some(l=>l.inputVersion!==sourceHash))throw new ApiError('Verified game inputs changed during this comparison. Refresh the individual evidence before joint research.',422);payload={game:p.game,simulations:count,seed:2026,inputContext:{...p.inputContext,contractDefinitions:contracts}};path='public/analyze';}
 const identity=createHash('sha256').update(JSON.stringify(['joint-probability-v10.2.1',sport,sourceHash,contracts,count])).digest('hex');
 const durable=await readProbabilitySimulation(sport,gameId,count,identity);if(durable?.jointSummary)return durable.jointSummary;
 const old=cache.get(identity);if(old&&old.until>Date.now())return old.value;
 const regional=process.env.VERCEL==='1'?getCache({namespace:'gridiron-probability-v10-2'}):null;
 // Runtime Cache contains only aggregate public statistical outputs, never a user's draft, identity or stake.
 try{const stored=await regional?.get(identity) as any;if(stored?.sourceHash===sourceHash&&stored.until>Date.now()&&stored.value?.simulations===count)return stored.value;}catch{}
 const endpoint=process.env.SIMULATION_SERVICE_URL,token=process.env.SIMULATION_SERVICE_TOKEN;if(!endpoint||!token||token.length<32)throw new ApiError('The private full-game worker is unavailable.',503);
 assertComputeAllowed();
 const lease=randomUUID(),reservation=await footballWrite({action:'reserve_compute',inputHash:identity,simulations:count,lease});if(reservation.execute!==true)throw new ApiError(reservation.status==='running'?'This aligned research is already running. Results will be retrieved when it finishes.':'The old aligned result expired before durable recovery was available. Reopen saved research or retry after the daily reservation resets.',reservation.status==='running'?409:503);
 try{const response=await fetch(new URL(path,endpoint.endsWith('/')?endpoint:endpoint+'/'),{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(payload),cache:'no-store',signal:AbortSignal.timeout(240000)});if(!response.ok)throw new ApiError('The complete-game worker could not verify these joint targets. Unsupported outcomes are withheld.',503);const result=(await response.json()).result;
 const sameFeatures=sport==='NFL'?typeof legs[0].modelFeatureVersion==='string'&&result?.baseFeatureVersion===legs[0].modelFeatureVersion&&legs.every(l=>l.modelFeatureVersion===legs[0].modelFeatureVersion)&&String(result.evidenceCutoff).slice(0,10)===String(legs[0].evidenceCutoff).slice(0,10):result?.inputDataVersion===(legs[0].modelDataVersion??legs[0].inputVersion);
 if(result?.home!==(sport==='NFL'?payload.game.home:payload.game.home.id)||result?.away!==(sport==='NFL'?payload.game.away:payload.game.away.id)||result?.simulations!==count||Date.parse(result.eventStart)!==Date.parse(legs[0].kickoff)||result.modelVersion!==legs[0].modelVersion||!sameFeatures||Date.parse(legs[0].kickoff)<=Date.now())throw new ApiError('Joint result identity did not match the verified model and kickoff.',502);
 const evaluated=simulationParlay(result,contracts.map(d=>d.id)),hits=evaluated.jointProbability*count;
 if(!Number.isSafeInteger(Math.round(hits))||Math.abs(hits-Math.round(hits))>1e-6||!evaluated.monteCarloInterval95)throw new ApiError('A reconciled unweighted joint outcome distribution is required.',422);
 const value={status:'ready',gameId,kickoff:legs[0].kickoff,rawProbability:evaluated.jointProbability,hits:Math.round(hits),simulations:count,monteCarloSE:Math.sqrt(evaluated.jointProbability*(1-evaluated.jointProbability)/count),monteCarloInterval95:evaluated.monteCarloInterval95,independenceComparison:evaluated.independenceProbability,pushProbability:evaluated.pushProbability,modelVersion:result.modelVersion,inputVersion:sourceHash,inputDataVersion:result.inputDataVersion,referenceModelDataVersion:legs[0].modelDataVersion,baseFeatureVersion:result.baseFeatureVersion??null,alignedMarginals:result.contracts.map((c:any)=>({id:c.id,probability:c.probability})),calculatedAt:result.createdAt,analysisId:identity,assumptions:legs.map(l=>l.assumptions),sources:legs.flatMap(l=>l.sources??[]),method:evaluated.method,reason:'Joint statistical threshold probability from aligned complete-game outcomes. Participation, push, void and actual platform combination settlement rules remain unverified.',market:{family:'hypothetical_combination',breakEven:null,fees:null}};
 const until=Math.min(Date.now()+30*60000,Date.parse(legs[0].kickoff));if(cache.size>=20)cache.delete(cache.keys().next().value!);cache.set(identity,{until,value});try{await regional?.set(identity,{sourceHash,until,value},{ttl:Math.max(1,Math.floor((until-Date.now())/1000)),tags:['public-joint-probability']});}catch{}
 await saveProbabilitySimulation(sport,gameId,count,identity,{result,jointSummary:value});
 await footballWrite({action:'complete_compute',id:reservation.id,lease});return value;
 }catch(error){await footballWrite({action:'fail_compute',id:reservation.id,lease}).catch(()=>{});throw error;}
}
