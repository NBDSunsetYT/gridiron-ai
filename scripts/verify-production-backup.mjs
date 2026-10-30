/** Verify a real HTTPS encrypted account export using disposable QA identities.
 * Run after research jobs finish; this test never mutates account records.
 * BASE_URL=https://... QA_CREDENTIALS_FILE=/private/qa.json
 * node --env-file=.env.local --import tsx scripts/verify-production-backup.mjs
 * Private artifacts go to /tmp; only aggregate verification results are saved
 * in docs/reports. The random backup password is never logged or persisted.
 */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {randomBytes,createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {EnvHttpProxyAgent,setGlobalDispatcher} from 'undici';
import {decryptBackup} from '../lib/backups.ts';
import {OWNED_TYPED_EXPORT_TABLES} from '../lib/cloud/export.ts';
import {validateCompleteGameResult} from './lib/simulation-workflow.mjs';

if(process.env.HTTPS_PROXY||process.env.HTTP_PROXY||process.env.https_proxy||process.env.http_proxy)setGlobalDispatcher(new EnvHttpProxyAgent());
const base=new URL(process.env.BASE_URL||'https://gridiron-ai-gray.vercel.app');
assert.equal(base.protocol,'https:','Use the actual HTTPS production origin.');
const credentials=JSON.parse(fs.readFileSync(process.env.QA_CREDENTIALS_FILE||'/tmp/gridiron-production-qa.json','utf8'));
const accounts=Array.isArray(credentials)?credentials:credentials.accounts;
assert.ok(Array.isArray(accounts)&&accounts.length>=2,'Two disposable accounts are required for the isolation assertion.');
for(const account of accounts.slice(0,2))assert.ok(account.id&&/qa/i.test(account.email)&&account.email.endsWith('@example.test'),'Only explicitly provisioned QA identities are accepted.');
const owner=accounts[0],other=accounts[1],cookies=new Map(),checks=[];
const mark=name=>{checks.push({name,status:'passed'});console.log(JSON.stringify({check:name,status:'passed'}));};
async function call(endpoint,body){
 const response=await fetch(new URL('/api/cloud/'+endpoint,base),{method:body===undefined?'GET':'POST',headers:{Origin:base.origin,'Content-Type':'application/json',Cookie:[...cookies].map(([key,value])=>key+'='+value).join('; ')},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(300000)});
 for(const value of response.headers.getSetCookie()){const first=value.split(';')[0],at=first.indexOf('=');cookies.set(first.slice(0,at),first.slice(at+1));}
 return response;
}
async function json(response){const data=await response.json();assert.ok(response.ok,typeof data.error==='string'?data.error:'Production API request failed');return data;}
const logged=await call('auth',{action:'login',email:owner.email,password:owner.password});
assert.match(logged.headers.get('set-cookie')||'',/HttpOnly/);assert.match(logged.headers.get('set-cookie')||'',/Secure/);
assert.equal((await json(logged)).user.id,owner.id);mark('Actual HTTPS authenticated QA session with secure HTTP-only cookies');
const before=await json(await call('ledger'));
assert.equal(before.summary.cashBalanceCents,Number(process.env.QA_EXPECTED_CASH_CENTS||52500));
assert.equal(before.summary.realizedPlCents,Number(process.env.QA_EXPECTED_PL_CENTS||7500));

// The export endpoint can stream large JSON responses. Count actual decoded HTTP
// response bytes, rather than inferring network support from a local unit test.
const password=randomBytes(48).toString('base64url');
const response=await call('ledger/backup',{password});
if(response.status!==200){const failure=await response.json().catch(()=>null);throw Error('Complete encrypted export HTTP '+response.status+': '+(typeof failure?.error==='string'?failure.error.slice(0,500):'Provider returned no structured application error.'));}
assert.match(response.headers.get('cache-control')||'',/private/);assert.match(response.headers.get('cache-control')||'',/no-store/);
assert.match(response.headers.get('content-disposition')||'',/attachment/);
const directory=fs.mkdtempSync(path.join(os.tmpdir(),'gridiron-production-backup-'));fs.chmodSync(directory,0o700);
const artifact=path.join(directory,'account-backup.encrypted.json'),fd=fs.openSync(artifact,'wx',0o600),chunks=[];
let bytes=0,chunkCount=0;
try{for await(const value of response.body){const chunk=Buffer.from(value);bytes+=chunk.length;assert.ok(bytes<=100_000_000,'Export exceeds its documented encrypted bound.');fs.writeSync(fd,chunk);chunks.push(chunk);chunkCount++;}}finally{fs.closeSync(fd);}
const raw=Buffer.concat(chunks),envelope=JSON.parse(raw.toString('utf8'));
assert.ok(['gridiron-encrypted-backup-v1','gridiron-encrypted-backup-v2'].includes(envelope.format));
assert.equal(envelope.cipher,'aes-256-gcm');assert.equal(envelope.kdf,'scrypt');
const restored=await decryptBackup(envelope,password);
assert.equal(restored.backend,'supabase');assert.equal(restored.email,owner.email);
mark('Production encrypted download authenticated and decrypted in memory');
const serialized=JSON.stringify(restored);
for(const account of accounts.slice(0,2))assert.ok(!serialized.includes(account.password),'Authentication passwords must not be exported.');
assert.ok(!serialized.includes(other.id)&&!serialized.includes(other.email),'Another account must not appear in this export.');
assert.ok(!/"(?:access_token|refresh_token|encrypted_password|sessions)"\s*:/.test(serialized),'No authentication credential/session fields may be exported.');
for(const cookie of cookies.values())assert.ok(!serialized.includes(cookie),'Server session cookies must not appear in export.');
assert.ok(!serialized.includes('_gridironGzipJson'),'Portable evidence must be completely decoded.');
mark('Other owner records, passwords, session credentials and compressed storage envelopes excluded');

assert.deepEqual(Object.keys(restored.research.typedTables).sort(),[...OWNED_TYPED_EXPORT_TABLES].sort());
for(const [table,rows] of Object.entries(restored.research.typedTables)){
 assert.ok(Array.isArray(rows),`Expected complete typed family ${table}.`);
 for(const row of rows)if('user_id'in row)assert.equal(row.user_id,owner.id,'Every typed record must belong to the authenticated owner.');
}
// Reconcile every family against actual owner-scoped database counts; there is
// no service-role key or privileged read in this verification.
const sbUrl=process.env.SUPABASE_URL,sbKey=process.env.SUPABASE_PUBLISHABLE_KEY;
assert.ok(sbUrl&&sbKey,'Supply the existing public Supabase connection for owner-scoped count verification.');
const accessToken=decodeURIComponent(cookies.get('gridiron_sb_access')||'');assert.ok(accessToken,'Expected server-authenticated owner token.');
async function ownedCount(table,extra=''){
 const countResponse=await fetch(new URL('/rest/v1/'+table+'?select=*&user_id=eq.'+owner.id+extra,sbUrl),{method:'HEAD',headers:{apikey:sbKey,Authorization:'Bearer '+accessToken,Prefer:'count=exact'},signal:AbortSignal.timeout(60000)});
 assert.ok(countResponse.ok,'Authenticated owned export count request failed.');
 const value=countResponse.headers.get('content-range');assert.ok(value&&/\/\d+$/.test(value),'Exact database count is required.');
 return Number(value.split('/').at(-1));
}
const typedEntries=Object.entries(restored.research.typedTables);
for(let start=0;start<typedEntries.length;start+=4){await Promise.all(typedEntries.slice(start,start+4).map(async([table,rows])=>assert.equal(rows.length,await ownedCount(table),`No pagination truncation for ${table}.`)));}
mark('All 43 normalized table families match exact live owner-scoped database counts');
assert.equal(restored.rawLedger.journal.length,restored.ledger.transactions.length);
assert.equal(restored.rawLedger.postings.reduce((sum,row)=>sum+BigInt(String(row.amount_cents)),0n),0n);
assert.equal(restored.ledger.summary.cashBalanceCents,before.summary.cashBalanceCents);
assert.equal(restored.ledger.summary.realizedPlCents,before.summary.realizedPlCents);
mark('Exact financial journal, balanced postings, cash and realized P/L reconcile');

for(const [table,rows] of [['conversations',restored.research.conversations],['conversation_messages',restored.research.conversation_messages]]){
 assert.ok(rows?.length>0,'Expected the saved QA conversation and user message.');assert.equal(rows.length,await ownedCount(table));
 for(const row of rows)assert.equal(row.user_id,owner.id);
}
for(const kind of ['simulation_inputs','simulation_jobs']){
 const rows=restored.research[kind];assert.ok(rows?.length>0,'Expected durable research '+kind);assert.equal(rows.length,await ownedCount('gridiron_records','&kind=eq.'+kind));
 for(const row of rows)assert.equal(row.user_id,owner.id);
}
const backgroundIds=new Set(restored.research.simulation_jobs.filter(job=>job.data?.execution==='background').map(job=>job.id));
for(const row of restored.research.simulation_inputs.filter(row=>backgroundIds.has(row.job_id))){
 assert.equal(row.inputProof?.version,1,'Background replay input receipt must remain in the archive.');assert.equal(row.inputProof?.algorithm,'hmac-sha256');assert.match(row.inputProof?.mac||'',/^[a-f0-9]{64}$/);
 const receiptResponse=await fetch(new URL('/rest/v1/gridiron_records?select=id,data->inputProof&id=eq.'+row.id+'&user_id=eq.'+owner.id,sbUrl),{headers:{apikey:sbKey,Authorization:'Bearer '+accessToken},signal:AbortSignal.timeout(60000)});
 assert.ok(receiptResponse.ok,'Owned input receipt readback must succeed.');const original=await receiptResponse.json();assert.equal(original.length,1);assert.deepEqual(row.inputProof,original[0].inputProof,'Portable input receipt must match the immutable stored receipt exactly.');
}
const fits=restored.research.simulation_jobs.filter(job=>job.kind==='fit'&&job.status==='completed');
assert.ok(fits.length>0,'Expected a complete original fitted model artifact.');
for(const fit of fits)assert.ok(fit.result?.model?.rows?.length>0,'The encrypted backup must contain full model rows, not a compact UI reference.');
assert.ok(restored.research.simulation_inputs.some(row=>row.data?.action==='fit'&&typeof row.data.csv==='string'&&row.data.csv.length>0),'Original fitted evidence CSV must survive export.');
const expectedCounts=(process.env.QA_REQUIRED_SIMULATION_COUNTS||'10000,50000,100000').split(',').map(Number),validated=[];
for(const count of expectedCounts){const job=restored.research.simulation_jobs.find(job=>job.kind==='simulate'&&job.status==='completed'&&job.result?.simulations===count);assert.ok(job,`Missing complete saved ${count}-game result.`);validateCompleteGameResult(job.result,count);validated.push(count);}
mark('Full original simulation inputs, fitted rows, complete-game outputs and conversation histories survive export');
const after=await json(await call('ledger'));assert.equal(after.summary.cashBalanceCents,before.summary.cashBalanceCents);assert.equal(after.summary.realizedPlCents,before.summary.realizedPlCents);
mark('Export and decryption leave financial records unchanged');
const report={status:'passed',checkedAt:new Date().toISOString(),baseUrl:base.origin,environment:'Actual HTTPS export from isolated SYNTHETIC QA owner; genuine historical model artifacts remain research evidence',checks,normalizedTableFamilies:OWNED_TYPED_EXPORT_TABLES.length,ownedConversations:restored.research.conversations.length,ownedMessages:restored.research.conversation_messages.length,simulationInputRecords:restored.research.simulation_inputs.length,simulationJobRecords:restored.research.simulation_jobs.length,completeGameModesValidated:validated,backupEnvelopeFormat:envelope.format,expandedBackupBytes:Buffer.byteLength(serialized),decodedHttpResponseBytes:bytes,responseChunks:chunkCount,exceeds4Point5MB:bytes>4_500_000,largeResponseVerification:bytes>4_500_000?'Actual production response exceeded 4.5 MB and downloaded completely.':'This account export stayed below 4.5 MB; production large-response behavior was not established by this run.',encryptedArtifactSha256:createHash('sha256').update(raw).digest('hex'),privateArtifactSaved:true,passwordLoggedOrPersisted:false,authenticationSecretsExcluded:true,otherOwnerExcluded:true,databaseRestoreAttempted:false,limitations:['Account export is not a full PostgreSQL/Auth/storage recovery point.','Typed records are complete in this archive; the current account importer does not reconstruct every normalized warehouse/model table.','No personal or production user account was changed.']};
const reportPath=process.env.QA_BACKUP_REPORT||'docs/reports/production-encrypted-backup.json';fs.mkdirSync(path.dirname(reportPath),{recursive:true});fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({status:'passed',checks:checks.length,bytes,largeResponseVerified:report.exceeds4Point5MB,report:reportPath,privateArtifact:artifact,secretsPrinted:false}));
