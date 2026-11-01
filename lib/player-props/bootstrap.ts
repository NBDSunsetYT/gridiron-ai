/** Server-only decoder for shared, whole-game parameter-bootstrap samples.
 * These intervals measure parameter sensitivity, not validated predictive coverage.
 */
import {gunzipSync} from 'node:zlib';
import {playerParameterHistograms} from './parameter-histograms';

export const PROP_PARAMETER_METHOD='Whole-historical-game Bayesian bootstrap parameter sensitivity; finite inner simulation noise is included. This is not calibrated predictive coverage.';
export const PROP_SAMPLE_ENCODING='gzip_base64_int32le_shared_player_stats_v1';
const MAX_RAW_BYTES=8_000_000,MAX_COMPRESSED_BYTES=2_000_000;
const STATS=new Set(['passingAttempts','completions','passingYards','passingTouchdowns','interceptions','targets','receptions','receivingYards','receivingTouchdowns','carries','rushingYards','rushingTouchdowns','touchdowns']);
const YARDS=new Set(['passingYards','receivingYards','rushingYards']);
type Row=Record<string,any>;
export type PropParameterDetails={interval95:[number,number]|null;status:'available'|'unavailable';method:string;reason?:string;replicates?:number;gamesPerReplicate?:number};
export type PropParameterSamples={players:string[];stats:string[];replicates:number;gamesPerReplicate:number;raw:Buffer;histogram?:(replicate:number,player:number,stat:number)=>Array<[number,number]>;value:(replicate:number,game:number,player:number,stat:number)=>number};
const decodedCache=new WeakMap<object,{encoded:string;metadata:string;samples:PropParameterSamples}>();

/** Missing or corrupt evidence is null, never an inferred all-zero player. */
export function decodePropParameterSamples(result:Row):PropParameterSamples|null{
 try{
  const bootstrap=result?.uncertainty?.parameterBootstrap;if(bootstrap?.playerHistograms!==undefined)return playerParameterHistograms(result);const samples=bootstrap?.playerSamples;
  if(!samples||samples.status!=='available'||samples.encoding!==PROP_SAMPLE_ENCODING||samples.valueType!=='int32le')return null;
  const metadata=JSON.stringify([samples.status,samples.encoding,samples.valueType,samples.players,samples.stats,samples.shape,samples.uncompressedBytes,samples.compressedBytes,bootstrap.replicates,bootstrap.gamesPerReplicate,bootstrap.completeGames,bootstrap.historicalGameBlocks]);
  const cached=decodedCache.get(samples);
  if(cached&&cached.encoded===samples.dataBase64&&cached.metadata===metadata)return cached.samples;
  const shape=samples.shape;if(!Array.isArray(shape)||shape.length!==4||shape.some(v=>!Number.isInteger(v)||v<=0))return null;
  const[replicates,gamesPerReplicate,playerCount,statCount]=shape;
  if(replicates<10||replicates>40||gamesPerReplicate<100||gamesPerReplicate>2000||playerCount>256||statCount>STATS.size)return null;
  if(bootstrap.replicates!==replicates||bootstrap.gamesPerReplicate!==gamesPerReplicate||bootstrap.completeGames!==replicates*gamesPerReplicate||!Number.isInteger(bootstrap.historicalGameBlocks)||bootstrap.historicalGameBlocks<8)return null;
  const players=samples.players,stats=samples.stats;
  if(!Array.isArray(players)||players.length!==playerCount||players.some(v=>typeof v!=='string'||!v||v.length>120)||new Set(players).size!==playerCount)return null;
  if(!Array.isArray(stats)||stats.length!==statCount||stats.some(v=>!STATS.has(v))||new Set(stats).size!==statCount)return null;
  const expected=replicates*gamesPerReplicate*playerCount*statCount*4;
  if(!Number.isSafeInteger(expected)||expected>MAX_RAW_BYTES||samples.uncompressedBytes!==expected)return null;
  if(typeof samples.dataBase64!=='string'||samples.dataBase64.length>2_666_668||samples.dataBase64.length%4!==0||!/^[A-Za-z0-9+/]+={0,2}$/.test(samples.dataBase64))return null;
  const compressed=Buffer.from(samples.dataBase64,'base64');
  if(compressed.length!==samples.compressedBytes||compressed.length>MAX_COMPRESSED_BYTES||compressed.toString('base64')!==samples.dataBase64)return null;
  const raw=gunzipSync(compressed,{maxOutputLength:expected});if(raw.length!==expected)return null;
  const statNames=stats as string[],playerNames=players as string[];
  for(let offset=0,index=0;offset<raw.length;offset+=4,index++){
   const value=raw.readInt32LE(offset),stat=statNames[index%statCount];
   if(Math.abs(value)>60_000||value<0&&!YARDS.has(stat))return null;
  }
  const value=(replicate:number,game:number,player:number,stat:number)=>{
   if(![replicate,game,player,stat].every(Number.isInteger)||replicate<0||replicate>=replicates||game<0||game>=gamesPerReplicate||player<0||player>=playerCount||stat<0||stat>=statCount)throw new RangeError('Bootstrap sample index is outside the verified shape.');
   return raw.readInt32LE((((replicate*gamesPerReplicate+game)*playerCount+player)*statCount+stat)*4);
  };
  // Derived touchdown totals must retain the same shared-game scorer events.
  const td=statNames.indexOf('touchdowns'),rush=statNames.indexOf('rushingTouchdowns'),receiving=statNames.indexOf('receivingTouchdowns');
  if(td>=0&&rush>=0&&receiving>=0)for(let r=0;r<replicates;r++)for(let g=0;g<gamesPerReplicate;g++)for(let p=0;p<playerCount;p++)if(value(r,g,p,td)!==value(r,g,p,rush)+value(r,g,p,receiving))return null;
  const decoded={players:playerNames,stats:statNames,replicates,gamesPerReplicate,raw,value};
  decodedCache.set(samples,{encoded:samples.dataBase64,metadata,samples:decoded});
  return decoded;
 }catch{return null;}
}

function predicate(value:number,threshold:number,operator:string):boolean|null{
 switch(operator){
  case'gt':case'over':case'>':case'above':return value>threshold;
  case'gte':case'>=':case'at_least':return value>=threshold;
  case'lt':case'under':case'<':case'below':return value<threshold;
  case'lte':case'<=':case'at_most':return value<=threshold;
  case'eq':case'=':case'==':return value===threshold;
  default:return null;
 }
}

/** Exact binary threshold outcomes within each independent parameter replicate.
 * Numeric pushes/voids need their separate settlement evaluator; this helper does
 * not turn an equality refund into a winning NO contract.
 */
export function propParameterInterval(result:Row,playerId:string,stat:string,threshold:number,operator:string,side:'yes'|'no'='yes',decoded?:PropParameterSamples|null):PropParameterDetails{
 const unavailable=(reason:string):PropParameterDetails=>({interval95:null,status:'unavailable',method:PROP_PARAMETER_METHOD,reason});
 if(typeof threshold!=='number'||!Number.isFinite(threshold)||!['yes','no'].includes(side)||predicate(0,threshold,operator)===null)return unavailable('The exact binary outcome definition is unsupported.');
 if(result?.publicPlayerForecastsWithheld?.[playerId])return unavailable('Current player availability evidence withholds this projection.');
 if(stat==='touchdowns'&&result?.statisticCoverage?.touchdowns!=='offensive_rushing_receiving_only')return unavailable('Player return/defensive touchdown coverage is not supplied.');
 const samples=decoded===undefined?decodePropParameterSamples(result):decoded;
 if(!samples)return unavailable('A reconciled, bounded whole-game player bootstrap is not available.');
 const player=samples.players.indexOf(playerId),column=samples.stats.indexOf(stat);
 if(player<0||column<0)return unavailable('This exact player/statistic is not explicitly represented in the parameter samples.');
 const probabilities:number[]=[];
 try{for(let replicate=0;replicate<samples.replicates;replicate++){
  let hits=0;if(samples.histogram){for(const[value,count]of samples.histogram(replicate,player,column)){const yes=predicate(value,threshold,operator)!;hits+=Number(side==='yes'?yes:!yes)*count;}}
  else for(let game=0;game<samples.gamesPerReplicate;game++){const yes=predicate(samples.value(replicate,game,player,column),threshold,operator)!;hits+=Number(side==='yes'?yes:!yes);}
  probabilities.push(hits/samples.gamesPerReplicate);
 }}catch{return unavailable('The parameter frequency evidence could not be verified.');}
 probabilities.sort((a,b)=>a-b);
 const interval95:[number,number]=[probabilities[Math.max(0,Math.floor(.025*probabilities.length))],probabilities[Math.min(probabilities.length-1,Math.ceil(.975*probabilities.length)-1)]];
 return{interval95,status:'available',method:PROP_PARAMETER_METHOD,replicates:samples.replicates,gamesPerReplicate:samples.gamesPerReplicate};
}
