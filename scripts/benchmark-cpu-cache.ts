/** Measures real codec CPU on an archived forecast; executes zero simulations. */
import {readFileSync,writeFileSync,readdirSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {immutableCache} from '../lib/performance/immutable-cache';
async function main(){const dir='artifacts/learning-v16/runs/reference-v15/CFB/',file=readdirSync(dir).filter(v=>v.endsWith('.forecast.json.gz')).sort()[0],compressed=readFileSync(dir+file),decoded=gunzipSync(compressed),n=400;
 const load=async()=>JSON.parse(gunzipSync(compressed).toString());
 const trial=async(cached:boolean)=>{let loads=0;const memo=immutableCache();const call=async()=>{loads++;return load();};const cpu=process.cpuUsage(),began=performance.now();let sum=0;for(let i=0;i<n;i++){const r=cached?await memo('verified-pointer',call,()=>decoded.length*3):await call();sum+=r.forecast.homeWinProbability;}const use=process.cpuUsage(cpu);return{cpuMs:(use.user+use.system)/1000,wallMs:performance.now()-began,loads,checksum:sum};};
 const before=await trial(false),after=await trial(true);assert.equal(before.checksum,after.checksum);
 const result={scope:'local immutable-object codec only; excludes database/network and football computation; not Vercel billed CPU',artifactSha256:createHash('sha256').update(compressed).digest('hex'),requests:n,artifactBytes:decoded.length,simulationsExecuted:0,before,after,cpuReductionPercent:100*(1-after.cpuMs/before.cpuMs),memory:process.memoryUsage(),createdAt:new Date().toISOString()};writeFileSync('docs/reports/cpu-cache-benchmark.json',JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));}
void main();
