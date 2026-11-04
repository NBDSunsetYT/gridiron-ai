import {freeProps} from '../free-props-service';
import {samePropSelection} from './market-identity';
import {alignedJoint} from './joint';
import {probabilityCapacity} from './capacity';
import {createHash} from 'node:crypto';
import type {ProbabilityTarget} from './schema';
/** Current research only. Never writes a wager or changes an original source quote. */
export async function automaticCombination(target:Extract<ProbabilityTarget,{type:'combination'}>){
 const cursors=[...new Set(target.legs.filter(l=>l.type==='prop').map(l=>l.cursor))],pages=await Promise.all(cursors.map(cursor=>freeProps(target.sport,cursor))),legs=target.legs.map(t=>{
  if(t.type!=='prop')return{status:'unavailable',reason:'Only verified player-prop definitions support automatic combination updates.'};
  const page=pages[cursors.indexOf(t.cursor)],matches=page.items.filter((r:any)=>samePropSelection(r,t.reference)),row=matches.length===1?matches[0]:null;
  if(!row||row.stale||row.state!=='ready')return{target:t,status:'pending',reason:row?.reason??'Waiting for this exact current player/event/threshold.'};
  return{target:t,status:'ready',method:row.method,rawProbability:row.method==='full_game_simulation'?row.rawProbability??row.modelProbability:null,posteriorProbability:row.posteriorProbability??null,empiricalProbability:row.empiricalProbability??null,calibratedProbability:row.calibratedProbability??null,gameId:row.modelGameId,kickoff:row.kickoff,modelVersion:row.modelVersion,inputVersion:row.inputVersion,modelDataVersion:row.modelDataVersion,modelFeatureVersion:row.modelFeatureVersion,evidenceCutoff:row.evidenceCutoff,calculatedAt:row.calculatedAt,definition:row.method==='full_game_simulation'?{kind:'player',playerId:row.modelPlayerId,stat:row.statistic,threshold:Number(row.threshold),direction:row.side==='Over'?'over':'under',equality:'push',period:'full_game_including_overtime'}:null,market:{family:'sportsbook_reference',book:row.book.key,americanOdds:row.americanOdds,current:row.marketCurrent!==false,sourceUpdatedAt:row.sourceUpdatedAt}};
 });
 let joint:any={status:'pending',rawProbability:null,reason:'Aligned joint outcomes are not available. Marginal probabilities are never multiplied to fill the gap.'};
 if(legs.every(l=>l.status==='ready'&&l.method==='full_game_simulation')&&new Set(legs.map(l=>l.gameId)).size===1){const cap=await probabilityCapacity();if(cap.used+10000<=cap.backgroundLimit)try{joint=await alignedJoint(target.sport,legs,10000);}catch(e){joint.reason=e instanceof Error?e.message:joint.reason;}else joint.reason='Background simulation capacity is reserved or exhausted. Individual estimates remain available; no joint probability was invented.';}
 const evidenceKey=createHash('sha256').update(JSON.stringify([legs,joint.rawProbability,joint.inputVersion])).digest('hex');
 return{automatic:true,sport:target.sport,evidenceKey,status:joint.status,rawProbability:joint.rawProbability??null,method:joint.method??null,simulations:joint.simulations??null,monteCarloInterval95:joint.monteCarloInterval95??null,reason:joint.reason,legs,checkedAt:new Date().toISOString()};
}
