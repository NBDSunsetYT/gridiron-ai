import {gunzipSync} from 'node:zlib';
import {isGameMarket,type PropMarketContract} from './market-types';
import {canonicalPropTeam} from './normalize';
import {PROP_PARAMETER_METHOD,type PropParameterDetails} from './bootstrap';
import {thresholdHit} from './math';

const decoded=new WeakMap<object,{encoded:string;meta:string;raw:Buffer;replicates:number;games:number;teams:string[]}>();
/** Shared score pairs, never independently drawn team/player statistics. */
export function gameParameterInterval(result:Record<string,any>,contract:PropMarketContract,side:'YES'|'NO'):PropParameterDetails{
 const unavailable=(reason:string):PropParameterDetails=>({status:'unavailable',interval95:null,method:PROP_PARAMETER_METHOD,reason});
 if(!isGameMarket(contract.stat)||!Number.isFinite(contract.threshold)||!contract.settlement.fullGame||!contract.settlement.overtimeIncluded)return unavailable('The exact full-game including overtime contract definition is unsupported.');
 try{
  const bootstrap=result?.uncertainty?.parameterBootstrap,s=bootstrap?.gameSamples;
  if(!s||s.status!=='available'||s.encoding!=='gzip_base64_int32le_shared_game_scores_v1'||s.valueType!=='int32le'||s.coverage!=='full_game_including_overtime')return unavailable('Whole-game score-pair bootstrap evidence is unavailable for this stored model version.');
  const shape=s.shape;if(!Array.isArray(shape)||shape.length!==3||shape.some(v=>!Number.isInteger(v)||v<=0)||shape[2]!==2||shape[0]<10||shape[0]>40||shape[1]<100||shape[1]>2000)return unavailable('The score bootstrap shape is invalid.');
  const[r,g]=shape;if(bootstrap.replicates!==r||bootstrap.gamesPerReplicate!==g||bootstrap.completeGames!==r*g||!Number.isInteger(bootstrap.historicalGameBlocks)||bootstrap.historicalGameBlocks<8)return unavailable('The bootstrap does not reconcile with its historical-game blocks.');
  if(!Array.isArray(s.teams)||s.teams.length!==2||s.teams[0]!==result.home||s.teams[1]!==result.away||s.teams[0]===s.teams[1])return unavailable('The bootstrap home/away score axes do not match the model result.');
  const expected=r*g*2*4,meta=JSON.stringify([shape,s.teams,s.uncompressedBytes,s.compressedBytes]);
  if(expected>640000||s.uncompressedBytes!==expected||typeof s.dataBase64!=='string'||s.dataBase64.length>1000000||s.dataBase64.length%4!==0||!/^[A-Za-z0-9+/]+={0,2}$/.test(s.dataBase64))return unavailable('The bounded score sample encoding is invalid.');
  let sample=decoded.get(s);if(!sample||sample.encoded!==s.dataBase64||sample.meta!==meta){const bytes=Buffer.from(s.dataBase64,'base64');if(bytes.length!==s.compressedBytes||bytes.toString('base64')!==s.dataBase64)return unavailable('The compressed score sample length is inconsistent.');const raw=gunzipSync(bytes,{maxOutputLength:expected});if(raw.length!==expected)return unavailable('The decompressed score sample length is inconsistent.');for(let i=0;i<raw.length;i+=4){const score=raw.readInt32LE(i);if(score<0||score>1000)return unavailable('Score samples contain unsupported values.');}sample={encoded:s.dataBase64,meta,raw,replicates:r,games:g,teams:s.teams};decoded.set(s,sample);}
  const team=canonicalPropTeam(contract.subject?.teamId??contract.team),home=team===canonicalPropTeam(result.home),away=team===canonicalPropTeam(result.away);if(contract.stat!=='totalPoints'&&!home&&!away)return unavailable('The contract team is not a participant in these shared games.');
  const probabilities:number[]=[];
  for(let replicate=0;replicate<r;replicate++){let hits=0;for(let game=0;game<g;game++){
   const offset=(replicate*g+game)*8,h=sample.raw.readInt32LE(offset),a=sample.raw.readInt32LE(offset+4),v=contract.stat==='totalPoints'?h+a:contract.stat==='teamTotal'?(home?h:a):home?h-a:a-h;
   let hit:boolean;if(contract.stat==='gameWinner'&&v===0){const tie=Number(contract.settlement.tiePayoutCents);if(!Number.isFinite(tie)||tie<0||tie>100)return unavailable('Tie payout is not supported.');hit=(side==='YES'?tie:100-tie)===100;}else{const yes=thresholdHit(v,contract.threshold,contract.operator);hit=side==='YES'?yes:!yes;}hits+=Number(hit);
  }probabilities.push(hits/g);}
  probabilities.sort((a,b)=>a-b);return{status:'available',interval95:[probabilities[Math.floor(.025*r)],probabilities[Math.min(r-1,Math.ceil(.975*r)-1)]],method:PROP_PARAMETER_METHOD,replicates:r,gamesPerReplicate:g};
 }catch{return unavailable('The score-pair bootstrap could not be verified.');}
}
