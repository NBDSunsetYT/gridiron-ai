import test from 'node:test';
import assert from 'node:assert/strict';
import {runSavedSimulation,receiverFromNormalizedCsv} from './lib/simulation-workflow.mjs';

function clientWith(responses){const calls=[];return{calls,async call(...args){calls.push(args);assert.ok(responses.length,'Unexpected HTTP call');return responses.shift();}};}
const completed=(result={simulations:10000})=>({status:200,data:{job:{id:'saved-job',status:'completed',result,provenanceVerified:true}}});
test('queued receipts wait through running to a verified persisted result',async()=>{
 const client=clientWith([{status:202,data:{id:'saved-job',pending:true}}, {status:200,data:{job:{id:'saved-job',status:'queued'}}}, {status:200,data:{job:{id:'saved-job',status:'running'}}},completed()]);
 const progress=[];const output=await runSavedSimulation(client,{action:'simulate'},{sleep:async()=>{},onProgress:value=>progress.push(value.status)});
 assert.equal(output.result.simulations,10000);assert.equal(output.asynchronous,true);assert.deepEqual(progress,['queued','running','completed']);assert.equal(client.calls.length,4);
});
test('compact fitted artifact remains a saved server reference',async()=>{
 const client=clientWith([{status:202,data:{id:'saved-job',pending:true}},completed({model:{sha256:'source-sha'},modelJobId:'saved-job',modelReferenceOnly:true})]);
 const output=await runSavedSimulation(client,{action:'fit'},{sleep:async()=>{}});
 assert.equal(output.result.modelReferenceOnly,true);assert.equal(output.result.modelJobId,'saved-job');assert.equal(output.result.model.rows,undefined);
});
test('completed but unverified asynchronous result is rejected',async()=>{
 const response=completed();response.data.job.provenanceVerified=false;
 const client=clientWith([{status:202,data:{id:'saved-job'}},response]);
 await assert.rejects(runSavedSimulation(client,{action:'simulate'}),/missing a verified/);
});
test('failed statistical job stays failed instead of inventing output',async()=>{
 const client=clientWith([{status:202,data:{id:'saved-job'}},{status:200,data:{job:{id:'saved-job',status:'failed',error:'Insufficient scenario evidence'}}}]);
 const output=await runSavedSimulation(client,{action:'simulate'});assert.equal(output.status,'failed');assert.match(output.error,/Insufficient/);assert.equal(output.result,undefined);
});
test('a submission HTTP failure is reported without polling',async()=>{
 const client=clientWith([{status:503,data:{error:'Private service unavailable'}}]);
 await assert.rejects(runSavedSimulation(client,{action:'fit'}),/submission HTTP 503/);assert.equal(client.calls.length,1);
});
test('transient saved read errors retry; authorization errors fail',async()=>{
 const client=clientWith([{status:202,data:{id:'saved-job'}},{status:503,data:{}},completed()]);
 assert.equal((await runSavedSimulation(client,{action:'simulate'},{sleep:async()=>{}})).status,'completed');
 await assert.rejects(runSavedSimulation(clientWith([{status:202,data:{id:'saved-job'}},{status:401,data:{error:'Authentication required'}}]),{action:'simulate'}),/read HTTP 401/);
});
test('deadline leaves persisted job intact and refuses a completion claim',async()=>{
 let tick=0;const client=clientWith([{status:202,data:{id:'saved-job'}},{status:200,data:{job:{id:'saved-job',status:'running'}}}]);
 await assert.rejects(runSavedSimulation(client,{action:'simulate'},{deadlineMs:1,now:()=>tick++,sleep:async()=>{tick+=5;}}),/no completion is claimed/);
});
test('synchronous service result remains supported',async()=>{
 const client=clientWith([{status:200,data:{id:'sync-job',status:'completed',simulations:10000}}]);assert.equal((await runSavedSimulation(client,{action:'simulate'})).result.simulations,10000);
});
test('CSV receiver selection handles JSON commas, multiline citations and escaped quotes',()=>{
 const csv='availability,offense,receiver_id,note\r\n"{""a"":""inactive"",""b"":""active""}",DAL,actual-gsis,"source\nwith ""quotes"""\r\n{},SEA,another,\r\n';
 assert.equal(receiverFromNormalizedCsv(csv,['DAL']),'actual-gsis');assert.equal(receiverFromNormalizedCsv(csv,['SEA']),'another');assert.equal(receiverFromNormalizedCsv(csv,['NYG']),null);
});
