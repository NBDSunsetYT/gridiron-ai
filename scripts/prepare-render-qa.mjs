/** Scoped disposable Auth fixtures. No live secret is printed or checked in.
 * --prepare creates encrypted local configuration and a time-limited source.
 * --provision invokes only the existing, separately authorized validation helper.
 * Restore that helper's original HTTP 410 body immediately after provisioning.
 */
import {randomBytes,randomUUID,createHash,createCipheriv,createDecipheriv} from 'node:crypto';
import {readFileSync,writeFileSync,mkdirSync,renameSync} from 'node:fs';
import {createInterface} from 'node:readline';
import {EnvHttpProxyAgent,setGlobalDispatcher} from 'undici';
const folder='artifacts/render-migration-v24/followup/private-qa';
function seal(data,key){const iv=randomBytes(12),c=createCipheriv('aes-256-gcm',key,iv),body=Buffer.concat([c.update(JSON.stringify(data)),c.final()]);return JSON.stringify({iv:iv.toString('base64'),tag:c.getAuthTag().toString('base64'),body:body.toString('base64')});}
export function readFixture(){const key=readFileSync(folder+'/configuration.key'),box=JSON.parse(readFileSync(folder+'/configuration.encrypted.json','utf8')),d=createDecipheriv('aes-256-gcm',key,Buffer.from(box.iv,'base64'));d.setAuthTag(Buffer.from(box.tag,'base64'));return{key,value:JSON.parse(Buffer.concat([d.update(Buffer.from(box.body,'base64')),d.final()]).toString())};}
if(process.argv.includes('--prepare')){
 mkdirSync(folder,{recursive:true,mode:0o700});const run=randomUUID(),capability=randomBytes(48).toString('base64url'),hash=createHash('sha256').update(capability).digest('hex'),expiresAt=Date.now()+10*60000,accounts=['a','b'].map(s=>({email:'qa-render-'+run+'-'+s+'@example.test',password:randomBytes(48).toString('base64url')})),key=randomBytes(32);
 const value={run,capability,expiresAt,accounts};writeFileSync(folder+'/configuration.key',key,{mode:0o600,flag:'wx'});writeFileSync(folder+'/configuration.encrypted.json',seal(value,key),{mode:0o600,flag:'wx'});
 const source=`import {createClient} from 'npm:@supabase/supabase-js@2.118.0';
const expectedHash=${JSON.stringify(hash)},allowed=${JSON.stringify(accounts.map(a=>a.email))},expiresAt=${expiresAt};
Deno.serve(async(req:Request)=>{
 const headers={'Cache-Control':'private, no-store'};if(req.method!=='POST')return Response.json({error:'POST required'},{status:405,headers});
 if(Date.now()>expiresAt)return Response.json({error:'Validation expired'},{status:410,headers});
 const capability=req.headers.get('x-gridiron-qa-capability')||'';
 if(capability.length!==64)return Response.json({error:'Validation capability required'},{status:401,headers});
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(capability)))).map(x=>x.toString(16).padStart(2,'0')).join('');let mismatch=0;for(let i=0;i<64;i++)mismatch|=hash.charCodeAt(i)^expectedHash.charCodeAt(i);
 if(mismatch)return Response.json({error:'Validation capability required'},{status:401,headers});
 try{
  const raw=await req.text();if(raw.length>3000)return Response.json({error:'Bounded validation input required'},{status:413,headers});const body=JSON.parse(raw);
  if(!Array.isArray(body.accounts)||body.accounts.length!==2||body.accounts.some((a:any,i:number)=>a.email!==allowed[i]||typeof a.password!=='string'||a.password.length<24||a.password.length>128))return Response.json({error:'Unexpected fixture identity'},{status:400,headers});
  const url=Deno.env.get('SUPABASE_URL'),secret=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');if(url!=='https://qdtdjbapdipopncklsdb.supabase.co'||!secret)return Response.json({error:'Validation service unavailable'},{status:503,headers});
  const admin=createClient(url,secret,{auth:{persistSession:false,autoRefreshToken:false}}),users=[];
  for(const a of body.accounts){const{data,error}=await admin.auth.admin.createUser({email:a.email,password:a.password,email_confirm:true,app_metadata:{gridiron_migration_qa:${JSON.stringify(run)}}});if(error||!data.user)return Response.json({error:'Could not provision complete fixture; no existing user was updated',createdCount:users.length},{status:502,headers});users.push({id:data.user.id,email:a.email});}
  return Response.json({users,scope:'New synthetic QA identities only; no email sent or existing user updated'},{headers});
 }catch{return Response.json({error:'Validation fixture failed'},{status:502,headers});}
});`;
 writeFileSync(folder+'/edge-source.ts',source,{mode:0o600,flag:'wx'});console.log(JSON.stringify({prepared:true,accounts:2,expiresAt,sourcePath:folder+'/edge-source.ts',credentialsEncrypted:true}));
}else if(process.argv.includes('--provision')||process.argv.includes('--check-disabled')){
 if(process.env.HTTPS_PROXY||process.env.HTTP_PROXY)setGlobalDispatcher(new EnvHttpProxyAgent());const input=createInterface({input:process.stdin});console.log('QA provision client ready for public anon JWT via private stdin.');
 input.once('line',async line=>{try{const{anon}=JSON.parse(line);
  if(process.argv.includes('--check-disabled')){const r=await fetch('https://qdtdjbapdipopncklsdb.supabase.co/functions/v1/gridiron-v6-validation-setup',{headers:{apikey:anon,Authorization:'Bearer '+anon},redirect:'error',signal:AbortSignal.timeout(10000)});if(r.status!==410)throw Error('Validation endpoint was not disabled');console.log(JSON.stringify({validationHelperDisabled:true,httpStatus:r.status}));return;}
  const{key,value}=readFixture();if(Date.now()>value.expiresAt||value.accounts.some(a=>a.id))throw Error('Fixture expired or already provisioned');const r=await fetch('https://qdtdjbapdipopncklsdb.supabase.co/functions/v1/gridiron-v6-validation-setup',{method:'POST',headers:{apikey:anon,Authorization:'Bearer '+anon,'Content-Type':'application/json','x-gridiron-qa-capability':value.capability},body:JSON.stringify({accounts:value.accounts}),redirect:'error',signal:AbortSignal.timeout(30000)});const body=await r.json();if(!r.ok||body.users?.length!==2||body.users.some((a,i)=>a.email!==value.accounts[i].email||!/^[a-f0-9-]{36}$/.test(a.id)))throw Error('Fixture provisioning failed');value.accounts.forEach((a,i)=>a.id=body.users[i].id);writeFileSync(folder+'/updated.encrypted.json',seal(value,key),{mode:0o600});renameSync(folder+'/updated.encrypted.json',folder+'/configuration.encrypted.json');writeFileSync(folder+'/provisioned.json',JSON.stringify({createdAt:new Date().toISOString(),accounts:2,scope:'Two new synthetic Auth identities; existing users unchanged',testedLogin:false},null,2),{mode:0o600});console.log(JSON.stringify({provisioned:true,accounts:2,credentialsEncrypted:true,existingUsersUpdated:0}));}catch{console.error('QA provisioning failed; no credentials are logged.');process.exitCode=1;}finally{input.close();}});
}
