import {ApiError} from './auth';

/** Injury references connect saved research records; only statistical assumptions
 * belong in the private engine request. Keep the original input for replay. */
export function simulationPayload(input:Record<string,any>,options:{replay?:boolean}={}){
 const {action: _action,injuryEntityKeys,injuryMixture,...payload}=input;
 if(injuryEntityKeys!==undefined&&(!Array.isArray(injuryEntityKeys)||injuryEntityKeys.length>100||injuryEntityKeys.some((id:unknown)=>typeof id!=='string'||!id.trim()||id.length>180)))throw new ApiError('Injury references must be an array of at most 100 stable entity IDs.');
 if(injuryMixture!==undefined){
  if(!options.replay)throw new ApiError('A saved injury-mixture recipe is replay metadata. Use an evidence-backed availability scenario rather than submitting a mixture as a game assumption.');
  const recipe=injuryMixture,scenarios=recipe?.scenarios;
  if(!recipe||typeof recipe!=='object'||Object.keys(recipe).some(key=>!['playerId','scenarios'].includes(key))||typeof recipe.playerId!=='string'||!recipe.playerId.trim()||recipe.playerId.length>180||!Array.isArray(scenarios)||scenarios.length<1||scenarios.length>3||scenarios.some((s:any)=>!s||Object.keys(s).some(key=>!['status','weight'].includes(key))||!['active','limited','inactive'].includes(s.status)||!Number.isFinite(s.weight)||s.weight<0||s.weight>1)||new Set(scenarios.map((s:any)=>s.status)).size!==scenarios.length||Math.abs(scenarios.reduce((n:number,s:any)=>n+s.weight,0)-1)>1e-9)throw new ApiError('The saved injury-mixture replay recipe is invalid. No assumptions were silently discarded.');
 }
 return payload;
}
