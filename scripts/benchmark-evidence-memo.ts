/** SYNTHETIC validation CPU microbenchmark. No games or prop forecasts simulated. */
import {createHash} from 'node:crypto';
import {writeFileSync,mkdirSync} from 'node:fs';
import assert from 'node:assert/strict';
import {attachAutomaticEvidence,automaticEvidenceMemo} from '../lib/probability/automatic-props';
const row={sport:'CFB',espnEventId:'123456789',eventId:'SYNTHETIC',player:{id:'espn:1'},kickoff:'2099-01-01T12:00:00Z',americanOdds:-110,statistic:'receivingYards',side:'Over',threshold:'40.5'};
const catalog=Array.from({length:80},(_,i)=>({id:'cfb:espn:'+String(i+1),name:'SYNTHETIC-'+i})),injuries=catalog.slice(1).map((p,i)=>({player_id:'espn:'+String(i+2),status_code:'out',source_updated_at:'2020-01-01T00:00:00Z'}));
const evidence={sport:'CFB',espnEventId:row.espnEventId,eventStart:row.kickoff,research:{playerCatalog:catalog},result:{players:Object.fromEntries(catalog.map(p=>[p.id,{receptions:{mean:1}}]))}},job={status:'queued'};
const measure=(cached:boolean)=>{const cpu=process.cpuUsage(),start=performance.now(),memo=cached?automaticEvidenceMemo(injuries):undefined;const results=Array.from({length:500},()=>attachAutomaticEvidence(row,evidence,job,injuries,memo));const usage=process.cpuUsage(cpu);return{cpuMs:(usage.user+usage.system)/1000,wallMs:performance.now()-start,sha256:createHash('sha256').update(JSON.stringify(results)).digest('hex')};};
// Warm the runtime, then alternate order to reduce one-sided JIT effects.
measure(false);measure(true);const rounds=Array.from({length:5},(_,i)=>{const a=i%2?measure(true):measure(false),b=i%2?measure(false):measure(true);return i%2?{before:b,after:a}:{before:a,after:b};});
for(const r of rounds)assert.equal(r.before.sha256,r.after.sha256);
const average=(key:'before'|'after',metric:'cpuMs'|'wallMs')=>rounds.reduce((n,r)=>n+r[key][metric],0)/rounds.length;
const result={scope:'Synthetic 500-row shared-game integrity audit only; not hosted CPU savings or forecast accuracy',gamesSimulated:0,probabilitiesNumericallyIdentical:true,beforeCpuMs:average('before','cpuMs'),afterCpuMs:average('after','cpuMs'),beforeWallMs:average('before','wallMs'),afterWallMs:average('after','wallMs'),rounds};mkdirSync('artifacts/render-migration-v24/followup',{recursive:true});writeFileSync('artifacts/render-migration-v24/followup/evidence-microbenchmark.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
