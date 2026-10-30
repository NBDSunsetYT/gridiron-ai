import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';

/** Runtime-only configuration. Never bake account secrets into the Next build. */
export function webEnvironment(input=process.env){
 const env={...input};
 const supplied=env.APP_URL|| (env.RAILWAY_PUBLIC_DOMAIN?`https://${env.RAILWAY_PUBLIC_DOMAIN}`:'');
 let origin;try{origin=new URL(supplied);}catch{throw Error('APP_URL or a generated Railway public domain must be configured before release.');}
 const loopback=['localhost','127.0.0.1','[::1]'].includes(origin.hostname),localTest=env.GRIDIRON_DEPLOY_TEST==='1'&&loopback;
 const placeholder=origin.hostname.endsWith('.example')||origin.hostname.endsWith('.invalid')||['example.com','example.org','example.net'].some(host=>origin.hostname===host||origin.hostname.endsWith('.'+host));
 if((origin.protocol!=='https:'&&!localTest)||loopback&&!localTest||origin.username||origin.password||origin.search||origin.hash||origin.pathname!=='/'||placeholder)throw Error('APP_URL must be the real HTTPS application origin.');
 if(!env.SUPABASE_URL||!env.SUPABASE_PUBLISHABLE_KEY)throw Error('Supabase server configuration is required for the hosted workspace.');
 if(env.SUPABASE_PUBLISHABLE_KEY.startsWith('sb_secret_'))throw Error('A Supabase secret/service-role key must never configure the user-scoped app client.');
 if(!env.SIMULATION_SERVICE_URL||!env.SIMULATION_SERVICE_TOKEN||env.SIMULATION_SERVICE_TOKEN.length<32)throw Error('The private simulation endpoint and stable server token are required.');
 const port=Number(env.PORT||8080);if(!Number.isInteger(port)||port<1||port>65535)throw Error('PORT must be a valid TCP port.');
 return{...env,APP_URL:origin.origin,HOSTNAME:'0.0.0.0',PORT:String(port),NODE_ENV:'production',DATA_BACKEND:'supabase',GRIDIRON_CLOUD_ONLY:'1',DATA_DIR:'/tmp/gridiron-hosted-cache'};
}
export function start(){
 let env;try{env=webEnvironment();}catch(error){console.error(error.message);process.exitCode=1;return;}
 const child=spawn(process.execPath,['server.js'],{cwd:'/app',env,stdio:'inherit'});
 for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>child.kill(signal));
 child.on('error',()=>{console.error('The production Next server could not start.');process.exitCode=1;});
 child.on('exit',(code,signal)=>{process.exitCode=code??(signal?1:0);});
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)start();
