import {createHash} from 'node:crypto';
import {canonicalJson} from '../cloud/attestation';

export type Sport='NFL'|'CFB';
export type ResearchKind='simulation'|'injury_snapshot'|'matchup_report'|'explanation'|'source_metadata';
export type ResearchDocument={_id:string;schemaVersion:1;sport:Sport;gameId:string;kind:ResearchKind;modelVersion:string|null;createdAt:string;sha256:string;bytes:number;payload:Record<string,any>};
export class ResearchIntegrityError extends Error{constructor(){super('Research document integrity check failed.');}}
const privateKey=/^(?:user|user_id|userId|owner_id|ownerId|account_id|accountId|email|password|authorization|cookie|api_?key|access_token|refresh_token|service_role_key|token|signature|resultProof|evidenceProof|bankroll|ledger|deposit|deposits|withdrawal|withdrawals|wager|wagers|settlement|settlements|accountBalance|balance|cashBalanceCents|pnl)$/i;
export function checksum(value:unknown){return createHash('sha256').update(canonicalJson(value)).digest('hex');}
function publicOnly(value:any,depth=0):boolean{if(depth>32)return false;if(value===undefined)return true;if(value===null||typeof value==='string'||typeof value==='boolean')return true;if(typeof value==='number')return Number.isFinite(value);if(Array.isArray(value))return value.length<=10000&&value.every(v=>v!==undefined&&publicOnly(v,depth+1));if(!value||typeof value!=='object')return false;return Object.entries(value).every(([k,v])=>!privateKey.test(k)&&publicOnly(v,depth+1));}
/** This boundary accepts shared football evidence only. It never accepts a private account export. */
export function researchDocument(sport:Sport,gameId:string,kind:ResearchKind,payload:Record<string,any>):ResearchDocument{
 if(!['NFL','CFB'].includes(sport)||!gameId||gameId.length>120||!['simulation','injury_snapshot','matchup_report','explanation','source_metadata'].includes(kind)||!publicOnly(payload))throw Error('Unsupported or private research payload.');
 const result=payload.result?.result??payload.result??payload;
 if(kind==='simulation')validateCompactSimulation(result);
 const raw=canonicalJson(payload),bytes=Buffer.byteLength(raw);if(bytes>2_000_000)throw Error('Research document exceeds the bounded document size; use a dataset reference.');
 const sha256=checksum(payload),_id=checksum({schemaVersion:1,sport,gameId,kind,sha256});
 const observed=typeof result.createdAt==='string'?result.createdAt:typeof payload.observedAt==='string'?payload.observedAt:new Date().toISOString();if(!Number.isFinite(Date.parse(observed)))throw Error('Research timestamp is invalid.');
 return{_id,schemaVersion:1,sport,gameId,kind,modelVersion:typeof result.modelVersion==='string'?result.modelVersion:null,createdAt:new Date(observed).toISOString(),sha256,bytes,payload:JSON.parse(raw)};
}
export function validateCompactSimulation(result:any){
 if(!result||!Number.isSafeInteger(result.simulations)||result.simulations<1||result.simulations>100000)throw Error('A completed aggregate simulation is required.');
 for(const field of ['games','allGames','simulatedGames','gameSamples','plays','playByPlay','rawSamples','rows'])if(result[field]!==undefined)throw Error('Per-game samples and play collections cannot enter permanent research storage.');
 if(!Array.isArray(result.representativeGames??[])||(result.representativeGames??[]).length>3)throw Error('At most three representative games can be retained.');
 for(const game of result.representativeGames??[])if(!Array.isArray(game.plays)||game.plays.length>1000)throw Error('Representative game trace exceeds the bounded inspection limit.');
 for(const distribution of Object.values(result.scoreDistributions??{}) as any[]){if(!Array.isArray(distribution.histogram)||distribution.histogram.some((b:any)=>!Number.isSafeInteger(b.count)||b.count<0)||distribution.histogram.reduce((n:number,b:any)=>n+b.count,0)!==result.simulations)throw Error('Score histogram does not reconcile to completed games.');}
 return result;
}
export function verifyResearchDocument(value:ResearchDocument,id:string,sha:string){if(value._id!==id||value.sha256!==sha||checksum(value.payload)!==sha||Buffer.byteLength(canonicalJson(value.payload))!==value.bytes)throw new ResearchIntegrityError();return value.payload;}
