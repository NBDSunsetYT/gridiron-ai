/** Explicit existing-service deployment. Never creates projects, starts login,
 * resets a database, prints credentials, or treats queued uploads as successful. */
import {spawn} from 'node:child_process';
import {readFile,mkdtemp,cp,rm,readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const ROOT=resolve(fileURLToPath(new URL('..',import.meta.url)));
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TOP=['app','components','lib','public','migrations','modeling','types','docs','deployment','package.json','package-lock.json','tsconfig.json','next-env.d.ts','next.config.ts','middleware.ts','instrumentation.ts','.dockerignore','.gitignore','.env.example','README.md'];
export function allowedSource(path){
 const parts=path.replaceAll('\\','/').split('/');
 return !parts.some(part=>['node_modules','data','backups','artifacts','ios','native','.git','.openai','__pycache__','.venv','xcuserdata'].includes(part)||part.startsWith('.next')||part.startsWith('.env')&&part!=='.env.example')&&!/\.(?:sqlite[^/]*|db|p12|p8|pem|key|mobileprovision|pyc)$/i.test(path);
}
export async function stageSource(){
 const target=await mkdtemp(join(tmpdir(),'gridiron-railway-source-'));
 const existing=new Set(await readdir(ROOT));
 for(const item of TOP)if(existing.has(item))await cp(join(ROOT,item),join(target,item),{recursive:true,filter:path=>allowedSource(path.slice(ROOT.length+1))});
 return target;
}
export function deploymentSelectors(env=process.env){
 const values={project:env.GRIDIRON_RAILWAY_PROJECT_ID,environment:env.GRIDIRON_RAILWAY_ENVIRONMENT_ID,web:env.GRIDIRON_RAILWAY_WEB_SERVICE_ID,quant:env.GRIDIRON_RAILWAY_QUANT_SERVICE_ID};
 if(Object.values(values).some(value=>!UUID.test(value??'')))throw Error('Explicit Railway project, environment and both existing service UUIDs are required.');
 if(env.RAILWAY_TOKEN&&env.RAILWAY_API_TOKEN)throw Error('Set only one Railway CLI authentication variable.');
 if(!env.RAILWAY_TOKEN&&!env.RAILWAY_API_TOKEN)throw Error('Railway account authorization is required. Configure one scoped CLI token through a trusted secret channel.');
 return values;
}
async function cli(args,input){
 return new Promise((resolve,reject)=>{
  const child=spawn(process.env.RAILWAY_BIN||'railway',args,{cwd:ROOT,env:{...process.env,CI:'true'},stdio:['pipe','pipe','pipe']});let output='',error='';
  child.stdout.on('data',chunk=>{output+=chunk;});child.stderr.on('data',chunk=>{error+=chunk;});child.on('error',()=>reject(Error('The pinned Railway CLI is not installed or could not start.')));
  child.on('exit',code=>code===0?resolve(output):reject(Error('Railway rejected the operation. Inspect its authenticated dashboard for account, billing, build or permission details; no raw secret-bearing output was printed.')));
  child.stdin.end(input??'');
 });
}
async function stdinJson(){let raw='';for await(const chunk of process.stdin){raw+=chunk;if(Buffer.byteLength(raw)>128000)throw Error('Configuration input is too large.');}return JSON.parse(raw);}
export async function main(mode=process.argv[2]||'--check'){
 if(!['--check','--stage','--configure','--upload'].includes(mode))throw Error('Use --check, --stage, --configure or --upload.');
 if(mode==='--stage'){console.log(JSON.stringify({sourcePath:await stageSource(),secretsIncluded:false}));return;}
 if(mode==='--check'){
  const pack=JSON.parse(await readFile(join(ROOT,'deployment/railway/package.json'),'utf8'));
  console.log(JSON.stringify({source:'existing GRIDIRON AI project',services:['web','quant'],cloudBackend:'Supabase',sdk:pack.dependencies.railway,requires:['authorized Railway account and billing review','existing service/project/environment UUIDs','server-only Supabase keys and stable quantitative token','real HTTPS web domain'],deployed:false}));return;
 }
 const ids=deploymentSelectors();
 if(mode==='--configure'){
  const values=await stdinJson();if(!values||typeof values!=='object')throw Error('A configuration object is required on stdin.');
  const allow={web:new Set(['SUPABASE_URL','SUPABASE_PUBLISHABLE_KEY','SIMULATION_SERVICE_TOKEN','APP_URL','DEVICE_TOKEN_ENCRYPTION_KEY','OPENAI_API_KEY','OPENAI_MODEL','ODDS_API_KEY']),quant:new Set(['SIMULATION_SERVICE_TOKEN'])};let count=0;
  if(values.web?.SIMULATION_SERVICE_TOKEN&&values.quant?.SIMULATION_SERVICE_TOKEN&&values.web.SIMULATION_SERVICE_TOKEN!==values.quant.SIMULATION_SERVICE_TOKEN)throw Error('Both services must preserve the same stable quantitative token.');
  for(const [service,variables]of Object.entries(values)){
   if(!allow[service]||!variables||typeof variables!=='object'||Array.isArray(variables))throw Error('Only explicit web/quant configuration objects are supported.');
   for(const[key,value]of Object.entries(variables)){
    if(!allow[service].has(key)||typeof value!=='string'||!value||value.length>16000)throw Error('Unsupported or invalid server configuration.');
    if(key==='SIMULATION_SERVICE_TOKEN'&&value.length<32)throw Error('A stable quantitative token must have at least 32 characters.');
    await cli(['variable','set',key,'--stdin','--skip-deploys','--json','--project',ids.project,'--environment',ids.environment,'--service',ids[service]],value);count++;
   }
  }
  console.log(JSON.stringify({configuredVariables:count,valuesPrinted:false,deploymentsTriggered:false}));return;
 }
 if(process.env.GRIDIRON_RAILWAY_BILLING_APPROVED!=='1')throw Error('Railway resource usage/billing must be reviewed and authorized before uploads.');
 const target=await stageSource();
 try{
  for(const service of ['quant','web']){
   await cli(['up',target,'--path-as-root','--detach','--json','--project',ids.project,'--environment',ids.environment,'--service',ids[service]]);
   console.log(JSON.stringify({service,status:'queued',verifiedHealthy:false}));
  }
 }finally{await rm(target,{recursive:true,force:true});}
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)main().catch(error=>{console.error(error.message);process.exitCode=1;});
