import {existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {standalonePaths} from './prepare-standalone.mjs';

export function webEnvironment(source=process.env){
 const env={...source,HOSTNAME:'0.0.0.0'};
 const port=Number(env.PORT||3000);
 if(!Number.isInteger(port)||port<1||port>65535)throw Error('PORT must be a valid HTTP port.');
 env.PORT=String(port);
 if(env.RENDER==='true'){
  // This entry point is the website, never a research worker. Fail closed on
  // ephemeral hosting even if an operator accidentally removes a policy flag.
  env.GRIDIRON_COMPUTE_ROLE='web';env.GRIDIRON_CLOUD_ONLY='1';env.DATA_BACKEND='supabase';
  env.GRIDIRON_WORKER_REQUEST_LIFETIME='0';env.GRIDIRON_ASYNC_SIMULATIONS='1';
  const missing=['SUPABASE_URL','SUPABASE_PUBLISHABLE_KEY'].filter(k=>!env[k]);
  if(missing.length)throw Error('Persistent authentication configuration missing: '+missing.join(', '));
  if(new URL(env.SUPABASE_URL).protocol!=='https:')throw Error('Persistent authentication requires HTTPS.');
  env.APP_URL=env.APP_URL||env.RENDER_EXTERNAL_URL;
  if(!env.APP_URL||new URL(env.APP_URL).protocol!=='https:')throw Error('APP_URL must be the intended HTTPS application origin.');
 }
 return env;
}
export function startWeb(){
 const env=webEnvironment(),paths=standalonePaths();
 if(!existsSync(paths.server))throw Error('Prepared standalone build is unavailable; run npm run build.');
 Object.assign(process.env,env);
 // Load in this process so Next receives SIGTERM directly; no wrapper child,
 // background loop, model import, local ledger migration or worker is started.
 createRequire(import.meta.url)(paths.server);
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))startWeb();
