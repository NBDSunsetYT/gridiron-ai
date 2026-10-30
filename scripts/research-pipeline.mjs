/** Owner-authenticated operator job. Never grants a cron secret arbitrary user access. */
import {existsSync,readFileSync,writeFileSync,chmodSync} from 'node:fs';
const origin=process.env.APP_ORIGIN||process.env.APP_URL,cookieFile=process.env.GRIDIRON_PIPELINE_COOKIE_FILE;
if(!origin)throw Error('Configure APP_URL to the real application origin.');
const url=new URL(origin);if(url.protocol!=='https:'&&!['localhost','127.0.0.1'].includes(url.hostname))throw Error('Pipeline scheduling requires HTTPS.');
let cookie=process.env.GRIDIRON_PIPELINE_OWNER_COOKIE||'';
if(cookieFile&&existsSync(cookieFile))cookie=readFileSync(cookieFile,'utf8').trim();
if(!cookie)throw Error('Provide your own authenticated session through GRIDIRON_PIPELINE_OWNER_COOKIE or a private GRIDIRON_PIPELINE_COOKIE_FILE. CRON_SECRET alone does not identify an owner.');
try{
 const response=await fetch(new URL('/api/pipeline',url),{method:'POST',headers:{'content-type':'application/json',cookie,origin:url.origin},body:JSON.stringify({action:'run'}),signal:AbortSignal.timeout(890000)});
 const data=await response.json();
 if(!response.ok)throw Error(response.status===401?'Owner session expired. Sign in again; no records were changed.':'The owned pipeline endpoint rejected the run.');
 if(cookieFile){const values=new Map(cookie.split(';').map(v=>v.trim().split(/=(.*)/s).slice(0,2)));for(const set of response.headers.getSetCookie?.()||[]){const part=set.split(';')[0],at=part.indexOf('=');values.set(part.slice(0,at),part.slice(at+1));}writeFileSync(cookieFile,Array.from(values,([name,value])=>`${name}=${value}`).join('; '),{mode:0o600});chmodSync(cookieFile,0o600);}
 console.log(JSON.stringify({skipped:Boolean(data.skipped),reason:data.reason??null,status:data.run?.status??null,steps:data.run?.steps?.map(s=>({name:s.name,status:s.status}))??[],nextRunAt:data.nextRunAt??null}));
}catch(error){console.error(error instanceof Error?error.message:'The owned pipeline did not complete.');process.exitCode=1;}
