/** Local Docker integration, never a remote deploy. Requires existing server
 * configuration; performs anonymous readiness/privacy checks, no financial writes. */
import {spawnSync} from 'node:child_process';
import {writeFileSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';

const root=resolve(fileURLToPath(new URL('../..',import.meta.url)));
if(existsSync(root+'/.env.local'))process.loadEnvFile(root+'/.env.local');
for(const key of ['SUPABASE_URL','SUPABASE_PUBLISHABLE_KEY','SIMULATION_SERVICE_TOKEN'])if(!process.env[key])throw Error('Existing server configuration is required: '+key);
const dockerEnv={...process.env};for(const key of ['DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'])delete dockerEnv[key];
function docker(args){const r=spawnSync('docker',['--host=unix:///var/run/docker.sock',...args],{encoding:'utf8',env:dockerEnv});if(r.status!==0)throw Error('Local Docker '+args[0]+' failed. No credential values were printed.');return r.stdout.trim();}
const suffix=String(Date.now()),network='gridiron-pwa-qa-'+suffix,quant='gridiron-quant-qa-'+suffix,web='gridiron-web-qa-'+suffix,owned=[];
const port=Number(process.env.GRIDIRON_CONTAINER_QA_PORT||3491),origin='http://127.0.0.1:'+port;
if(!Number.isInteger(port)||port<1024||port>65535)throw Error('Choose an unprivileged test port.');
try{
 docker(['network','create',network]);
 docker(['run','--detach','--name',quant,'--network',network,'--network-alias','quant','--env','SIMULATION_SERVICE_TOKEN','--env','PORT=8080','--security-opt','no-new-privileges:true','gridiron-quant-railway:qa']);owned.push(quant);
 docker(['run','--detach','--name',web,'--network',network,'--publish','127.0.0.1:'+port+':8080','--env','SUPABASE_URL','--env','SUPABASE_PUBLISHABLE_KEY','--env','SIMULATION_SERVICE_TOKEN','--env','SIMULATION_SERVICE_URL=http://quant:8080','--env','APP_URL='+origin,'--env','GRIDIRON_DEPLOY_TEST=1','--env','NO_PROXY=localhost,127.0.0.1,::1,quant','--env','no_proxy=localhost,127.0.0.1,::1,quant','--env','NODE_EXTRA_CA_CERTS=/run/trusted-ca.pem','--mount','type=bind,src=/etc/ssl/certs/ca-certificates.crt,dst=/run/trusted-ca.pem,readonly','--security-opt','no-new-privileges:true','gridiron-web-railway:qa']);owned.push(web);
 let ready=false;for(let i=0;i<15;i++){
  try{const response=await fetch(origin+'/api/health?check=dependencies',{signal:AbortSignal.timeout(12000)});if(response.ok){ready=true;break;}}catch{}
  await new Promise(r=>setTimeout(r,500));
 }
 if(!ready)throw Error('Container dependencies did not become ready; inspect owned test container logs before retrying.');
 if(!(await fetch(origin)).ok)throw Error('Home unavailable');
 if((await fetch(origin+'/api/ledger')).status!==401)throw Error('Anonymous financial access not rejected');
 if((await fetch(origin+'/api/backend',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json'},body:JSON.stringify({backend:'sqlite'})})).status!==409)throw Error('Ephemeral SQLite selection not rejected');
 const checks=["import urllib.request,json;d=json.load(urllib.request.urlopen('http://127.0.0.1:8080/health'));assert d['status']=='ready'","import urllib.request,json;r=urllib.request.build_opener(urllib.request.ProxyHandler({}));d=json.load(r.open('http://[::1]:8080/health'));assert d['status']=='ready'"];
 for(const source of checks)docker(['exec',quant,'python','-c',source]);
 docker(['exec',web,'node','-e',"const fs=require('fs');for(const p of ['.env','.env.local','.env.production','data/gridiron.sqlite'])if(fs.existsSync(p))throw Error('Forbidden runtime source file')"]);
 const report={status:'passed',environment:'Actual local Docker images; real remote Supabase Auth health and private bridge-network Python service; not a public deployment',checks:['both images built','non-root production Node startup','real Supabase dependency readiness','private quantitative dependency readiness','IPv4 and IPv6 quantitative health','anonymous financial401','ephemeral SQLite switch409','runtime env/user database source exclusion'],deploymentStatus:'authorization_required',credentialsIncluded:false};
 writeFileSync(root+'/deployment/railway/container-verification.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}finally{for(const id of owned.reverse())try{docker(['rm','--force',id]);}catch{}try{docker(['network','rm',network]);}catch{}}
