import {createHmac,timingSafeEqual} from 'node:crypto';
import {getCache} from '@vercel/functions';
import {canonicalJson} from '../cloud/attestation';
import {validateCollegeGameResult} from './result';
import type {CollegeGame,CollegeAnalysis,CollegeSource,CollegeTeam} from './types';

// Hobby Runtime Cache is team-scoped. This fixed project + database namespace
// prevents accidental sharing with another project; no request chooses it.
const NAMESPACE='gridiron-ai:qdtdjbapdipopncklsdb:cfb-public-v1';
const MAX_BYTES=2_000_000,MAX_INDEX=10;
const privateKey=/^(?:ctx|user|user_id|userId|email|password|authorization|cookie|api_?key|access_token|accessToken|refresh_token|refreshToken|service_role_key|serviceRoleKey|token|signature|resultProof|evidenceProof|inputProof|bankroll|deposits|withdrawals)$/i;
const resultFields=['sport','modelVersion','engineVersion','rulesVersion','rules','inputDataVersion','provenance','evidenceCutoff','eventStart','simulations','seed','scenario','home','away','homeWinProbability','awayWinProbability','tieProbability','calibratedProbability','monteCarloInterval95','distributionEncoding','scoreDistributions','totalDistribution','marginDistribution','players','contracts','jointOutcomes','representativeGames','convergence','gameEnvironment','evidence','statisticCoverage','uncertainty','limitations','createdAt'];
const researchFields=['version','sources','playerCatalog','rejectedCounts','latestTeamEvidenceAt','historicalGameIds','injuryImpact','dataAvailabilityVerified','calibrationStatus'];
type PublicEntry={version:1;expiresAt:number;game:CollegeGame;analysis:CollegeAnalysis};
export type PublicCollegeCacheRef={gameId:string;simulations:number;inputHash:string;analysisId:string;expiresAt:number};
function client(){return process.env.VERCEL==='1'?getCache({namespace:NAMESPACE,namespaceSeparator:':' as const}):null;}
function secret(){const value=process.env.SIMULATION_SERVICE_TOKEN;return value&&value.length>=32?value:null;}
function mac(value:unknown,key:string){return createHmac('sha256',key).update('GRIDIRON-PUBLIC-CFB-CACHE-V1\n').update(canonicalJson(value)).digest('hex');}
function sealed(value:unknown,key:string){return{value,mac:mac(value,key)};}
function verified(envelope:any,key:string){if(!envelope||typeof envelope.mac!=='string'||!/^[a-f0-9]{64}$/.test(envelope.mac))return null;const a=Buffer.from(mac(envelope.value,key),'hex'),b=Buffer.from(envelope.mac,'hex');return a.length===b.length&&timingSafeEqual(a,b)?envelope.value:null;}
function safe(value:any):boolean{if(!value||typeof value!=='object')return true;if(Array.isArray(value))return value.every(safe);return Object.entries(value).every(([key,entry])=>!privateKey.test(key)&&safe(entry));}
function pick(value:any,keys:readonly string[]){return Object.fromEntries(keys.filter(key=>value?.[key]!==undefined).map(key=>[key,value[key]]));}
function source(value:CollegeSource){return pick(value,['id','name','url','collectedAt','publishedAt','availableAt','version','status','note']) as CollegeSource;}
function team(value:CollegeTeam){return pick(value,['id','providerId','espnId','name','abbreviation','score','ranking','conference','classification','record']) as CollegeTeam;}
function publicGame(value:CollegeGame):CollegeGame{return{...pick(value,['id','sport','espnId','providerIds','season','week','startTime','kickoffVerified','status','statusMessage','venue','neutralSite','conferenceGame']),home:team(value.home),away:team(value.away),sources:value.sources.map(source)} as CollegeGame;}
function key(gameId:string,count:number){return'game:'+gameId+':'+count;}
function eligible(game:CollegeGame){return game.sport==='CFB'&&/^cfb:espn:\d{6,12}$/.test(game.id)&&game.status==='scheduled'&&game.kickoffVerified===true&&Date.parse(game.startTime)>Date.now()&&!/postpon|cancel/i.test(game.statusMessage);}
function validate(entry:any,game:CollegeGame,count:number,inputHash:string):entry is PublicEntry{
 if(!eligible(game)||entry?.version!==1||!Number.isFinite(entry.expiresAt)||entry.expiresAt<=Date.now()||entry.expiresAt>Date.parse(game.startTime)||entry.game?.id!==game.id||entry.game?.sport!=='CFB'||entry.game?.home?.id!==game.home.id||entry.game?.away?.id!==game.away.id||Date.parse(entry.game.startTime)!==Date.parse(game.startTime)||!safe(entry))return false;
 const a=entry.analysis;if(a?.sport!=='CFB'||a.gameId!==game.id||a.status!=='completed'||a.stale!==false||a.persistent!==false||a.historySaved!==false||!/^[-a-f0-9]{36}$/i.test(a.id)||a.simulations!==count||a.inputVersion!==inputHash||!/^[a-f0-9]{64}$/.test(inputHash)||!Number.isFinite(Date.parse(a.createdAt))||entry.expiresAt>Date.parse(a.createdAt)+3600000||a.result?.inputDataVersion!==inputHash)return false;
 try{validateCollegeGameResult(a.result,game,count);return true;}catch{return false;}
}
/** Ephemeral public research only. A cache acknowledgment is not a private save. */
export async function cachePublicCollegeAnalysis(game:CollegeGame,analysis:CollegeAnalysis){
 try{const cache=client(),keySecret=secret();if(!cache||!keySecret||!eligible(game)||analysis.status!=='completed'||analysis.stale||!analysis.result)return false;
 const data:PublicEntry={version:1,expiresAt:Math.min(Date.now()+3600000,Date.parse(analysis.createdAt)+3600000,Date.parse(game.startTime)),game:publicGame(game),analysis:{...pick(analysis,['id','gameId','sport','status','simulations','modelVersion','inputVersion','createdAt','updatedAt']),result:pick(analysis.result,resultFields),research:pick(analysis.research,researchFields),stale:false,persistent:false,historySaved:false} as CollegeAnalysis};
 if(!validate(data,game,analysis.simulations,analysis.inputVersion??''))return false;
 const envelope=sealed(data,keySecret),ttl=Math.floor((data.expiresAt-Date.now())/1000);if(ttl<1||Buffer.byteLength(JSON.stringify(envelope),'utf8')>MAX_BYTES)return false;
 await cache.set(key(game.id,analysis.simulations),envelope,{ttl,tags:['cfb-public-results'],name:'public-cfb-complete-game-research'});
 const prior=await readPublicCollegeCacheIndex(),ref:PublicCollegeCacheRef={gameId:game.id,simulations:analysis.simulations,inputHash:analysis.inputVersion!,analysisId:analysis.id,expiresAt:data.expiresAt},index=[ref,...prior.filter(row=>row.gameId!==ref.gameId||row.simulations!==ref.simulations)].slice(0,MAX_INDEX);
 await cache.set('recent',sealed(index,keySecret),{ttl:3600,tags:['cfb-public-results'],name:'public-cfb-result-index'});return true;
 }catch{return false;}
}
export async function readPublicCollegeAnalysis(game:CollegeGame,count:number,inputHash:string):Promise<CollegeAnalysis|null>{
 try{const cache=client(),keySecret=secret();if(!cache||!keySecret)return null;const entry=verified(await cache.get(key(game.id,count)),keySecret);if(!validate(entry,game,count,inputHash))return null;return structuredClone(entry.analysis);}catch{return null;}
}
export async function readPublicCollegeCacheIndex():Promise<PublicCollegeCacheRef[]>{
 try{const cache=client(),keySecret=secret();if(!cache||!keySecret)return[];const index=verified(await cache.get('recent'),keySecret);return Array.isArray(index)?index.filter(row=>row&&/^cfb:espn:\d{6,12}$/.test(row.gameId)&&[10000,50000,100000].includes(row.simulations)&&/^[a-f0-9]{64}$/.test(row.inputHash)&&/^[-a-f0-9]{36}$/i.test(row.analysisId)&&Number.isFinite(row.expiresAt)&&row.expiresAt>Date.now()).slice(0,MAX_INDEX):[];}catch{return[];}
}
