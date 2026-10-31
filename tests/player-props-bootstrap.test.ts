import {describe,it,expect} from 'vitest';
import {gzipSync} from 'node:zlib';
import {decodePropParameterSamples,propParameterInterval,PROP_SAMPLE_ENCODING} from '../lib/player-props/bootstrap';

/** Explicit SYNTHETIC transport/mechanics, never NFL calibration evidence. */
function fixture(){
 const raw=Buffer.alloc(10*100*2*2*4);let offset=0;
 for(let r=0;r<10;r++)for(let game=0;game<100;game++){
  const value=game<10*(r+1)?65:64;
  for(const n of[value,0,value,0]){raw.writeInt32LE(n,offset);offset+=4;}
 }
 const compressed=gzipSync(raw);
 return{simulations:10000,uncertainty:{parameterBootstrap:{replicates:10,gamesPerReplicate:100,completeGames:1000,historicalGameBlocks:13,
  playerSamples:{status:'available',encoding:PROP_SAMPLE_ENCODING,valueType:'int32le',players:['SYNTH-QB','SYNTH-WR'],stats:['receivingYards','interceptions'],shape:[10,100,2,2],uncompressedBytes:raw.length,compressedBytes:compressed.length,dataBase64:compressed.toString('base64')}}}};
}
describe('Bounded complete-game prop parameter samples',()=>{
 it('evaluates exact thresholds and YES/NO separately across whole-game replicates',()=>{
  const result=fixture(),decoded=decodePropParameterSamples(result)!;
  expect(decoded.value(0,0,0,0)).toBe(decoded.value(0,0,1,0));
  const yes=propParameterInterval(result,'SYNTH-WR','receivingYards',64.5,'gt','yes',decoded),no=propParameterInterval(result,'SYNTH-WR','receivingYards',64.5,'gt','no',decoded);
  expect(yes.status).toBe('available');expect(yes.interval95).toEqual([.1,1]);expect(no.interval95).toEqual([0,.9]);
  expect(yes.method).toMatch(/not calibrated predictive coverage/i);
  expect(propParameterInterval(result,'SYNTH-WR','receivingYards',64,'gte').interval95).toEqual([1,1]);
  expect(propParameterInterval(result,'SYNTH-WR','receivingYards',64,'gt').interval95).toEqual([.1,1]);
 });
 it('does not narrow parameter sensitivity when the base game count increases',()=>{
  const result=fixture();expect(propParameterInterval(result,'SYNTH-WR','receivingYards',64.5,'gt')).toEqual(propParameterInterval({...result,simulations:100000},'SYNTH-WR','receivingYards',64.5,'gt'));
 });
 it('distinguishes explicit zero events from a missing player or statistic',()=>{
  const result=fixture();expect(propParameterInterval(result,'SYNTH-WR','interceptions',.5,'gt').interval95).toEqual([0,0]);
  for(const[player,stat]of[['SYNTH-MISSING','receivingYards'],['SYNTH-WR','passingAttempts']])expect(propParameterInterval(result,player,stat,.5,'gt')).toMatchObject({status:'unavailable',interval95:null});
  expect(propParameterInterval({...result,publicPlayerForecastsWithheld:{'SYNTH-WR':'SYNTHETIC unresolved availability'}},'SYNTH-WR','receivingYards',.5,'gt').interval95).toBeNull();
 });
 it('rejects corrupt, oversized, truncated and dimensionally inconsistent evidence',()=>{
  for(const change of[{dataBase64:'NOT_A_VALID_BASE64_VALUE'},{uncompressedBytes:8_000_001},{shape:[10,100,3,2]},{players:['SYNTH-WR','SYNTH-WR']},{compressedBytes:1},{encoding:'chart_histogram_bins_v1'}]){
   const result=fixture();Object.assign(result.uncertainty.parameterBootstrap.playerSamples,change);expect(decodePropParameterSamples(result)).toBeNull();expect(propParameterInterval(result,'SYNTH-WR','receivingYards',64.5,'gt').interval95).toBeNull();
  }
  const result=fixture(),large=Buffer.alloc(100000);const compressed=gzipSync(large);Object.assign(result.uncertainty.parameterBootstrap.playerSamples,{dataBase64:compressed.toString('base64'),compressedBytes:compressed.length});expect(decodePropParameterSamples(result)).toBeNull();
 });
 it('withholds unsupported operators and absent bootstrap artifacts',()=>{
  expect(propParameterInterval({},'SYNTH-WR','receivingYards',64.5,'gt').status).toBe('unavailable');
  expect(propParameterInterval(fixture(),'SYNTH-WR','receivingYards',64.5,'guessed')).toMatchObject({status:'unavailable',interval95:null});
 });
 it('reuses validated samples across many contracts but rechecks changed metadata',()=>{
  const result=fixture(),first=decodePropParameterSamples(result);
  expect(decodePropParameterSamples(result)).toBe(first);
  result.uncertainty.parameterBootstrap.playerSamples.uncompressedBytes+=4;
  expect(decodePropParameterSamples(result)).toBeNull();
 });
});
