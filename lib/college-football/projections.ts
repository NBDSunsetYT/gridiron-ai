import type {CollegeAnalysis,CollegeGame} from './types';

const roles:Record<string,string[]>={passingYards:['passer'],passingAttempts:['passer'],completions:['passer'],passingTouchdowns:['passer'],interceptions:['passer'],rushingYards:['rusher'],carries:['rusher'],rushingTouchdowns:['rusher'],receivingYards:['receiver'],receptions:['receiver'],receivingTouchdowns:['receiver'],touchdowns:['rusher','receiver']};
/** Independent distributions are actual calculated outcomes, not invented
 * market contracts. No line, price, book settlement probability or EV is added. */
export function collegePlayerProjections(game:CollegeGame,analysis:CollegeAnalysis,now=Date.now()){
 const result=analysis.result,starts=Date.parse(game.startTime);
 if(game.sport!=='CFB'||game.status!=='scheduled'||game.kickoffVerified!==true||analysis.sport!=='CFB'||analysis.gameId!==game.id||analysis.status!=='completed'||analysis.stale||!Number.isFinite(starts)||starts<=now||!result||result.sport!=='CFB'||Date.parse(result.eventStart)!==starts||!String(result.modelVersion).startsWith('cfb-')||!String(result.engineVersion).startsWith('cfb-')||result.home!==game.home.id||result.away!==game.away.id||![10000,50000,100000].includes(result.simulations)||result.simulations!==analysis.simulations||!Number.isFinite(result.homeWinProbability)||!Number.isFinite(result.awayWinProbability)||Math.abs(result.homeWinProbability+result.awayWinProbability-1)>1e-9)return[];
 const catalog=analysis.research?.playerCatalog??result.research?.playerCatalog??result.playerCatalog;
 if(!Array.isArray(catalog))return[];
 const output:Array<Record<string,any>>=[];
 for(const player of catalog){
  if(!player||typeof player.id!=='string'||!/^cfb:espn:\d+$/.test(player.id)||typeof player.name!=='string'||!player.name.trim()||![game.home.id,game.away.id].includes(player.team))continue;
  const stats=result.players?.[player.id],observedRoles=Array.isArray(player.observedRoles)?player.observedRoles:[];if(!stats)continue;
  for(const[stat,allowed]of Object.entries(roles)){
   if(!allowed.some(role=>observedRoles.includes(role)))continue;
   const distribution=stats[stat];if(!distribution||!Array.isArray(distribution.histogram)||!distribution.histogram.length||!Number.isFinite(distribution.mean))continue;
   let count=0,total=0,valid=true;const seen=new Set<number>();
   for(const bin of distribution.histogram){if(!bin||!Number.isFinite(bin.value)||!Number.isInteger(bin.count)||bin.count<0||seen.has(bin.value)){valid=false;break;}seen.add(bin.value);count+=bin.count;total+=bin.value*bin.count;}
   if(!valid||count!==result.simulations||Math.abs(total/count-distribution.mean)>1e-6)continue;
   const range=distribution.interval90;if(!Array.isArray(range)||range.length!==2||!range.every(Number.isFinite)||range[0]>range[1])continue;
   output.push({id:`${analysis.id}:${player.id}:${stat}`,sport:'CFB',dataFamily:'independent_projection',gameId:game.id,analysisId:analysis.id,player:{id:player.id,name:player.name,team:player.team,position:player.position??null},opponent:player.team===game.home.id?game.away:game.home,stat,mean:distribution.mean,median:Number.isFinite(distribution.median)?distribution.median:null,interval90:range,simulations:result.simulations,modelVersion:result.modelVersion,inputVersion:result.inputDataVersion??analysis.inputVersion,threshold:null,marketPrice:null,bookmaker:null,calibratedProbability:null,expectedValue:null,createdAt:analysis.createdAt,availabilityVerified:result.evidence?.availabilityVerified===true,basis:'Historical CFB complete-game baseline conditional on the modeled player opportunities; current availability and model calibration are incomplete.'});
  }
 }
 return output.sort((a,b)=>a.player.name.localeCompare(b.player.name)||a.stat.localeCompare(b.stat)).slice(0,120);
}
