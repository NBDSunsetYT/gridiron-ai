/** Operator-only recovery of public-football fitted input; no private accounts. */
import {writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
import {EnvHttpProxyAgent,setGlobalDispatcher} from 'undici';
import {learningRecord,learningPayload} from '../lib/learning/store';
import {sharedCache} from '../lib/public-nfl/store';
import {readResearchObject} from '../lib/public-nfl/objects';
async function main(){if(process.env.HTTPS_PROXY)setGlobalDispatcher(new EnvHttpProxyAgent());const id=process.argv[2];if(!/^[a-f0-9]{64}$/.test(id??''))throw Error('An archived forecast ID is required.');const row=await learningRecord(id);if(row?.kind!=='forecast')throw Error('Choose a frozen forecast.');const f:any=await learningPayload(row),expected=f.result.runManifest?.inputArtifactSha256;if(!/^[a-f0-9]{64}$/.test(expected))throw Error('Exact fitted input provenance unavailable.');const s=await sharedCache('analysis','gafie-replay:'+expected);if(!s?.data.reference)throw Error('No verified fitted artifact is archived.');const a=await readResearchObject(s.data.reference),raw=gunzipSync(Buffer.from(a.body,'base64'),{maxOutputLength:5_000_000});if(createHash('sha256').update(raw).digest('hex')!==expected)throw Error('Fitted artifact checksum mismatch');writeFileSync('/tmp/gridiron-gafie-recovered-model.json',raw,{mode:0o600});writeFileSync('/tmp/gridiron-gafie-recovered-forecast.json',JSON.stringify(f),{mode:0o600});console.log('Verified exact fitted model retrieved from persistent object storage.');}
main().catch(e=>{console.error(e instanceof Error?e.message:'Replay recovery failed.');process.exitCode=1;});
