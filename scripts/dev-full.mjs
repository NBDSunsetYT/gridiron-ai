/** Local two-service launcher. Existing configuration and user data are preserved. */
import {existsSync,readFileSync,appendFileSync,chmodSync} from 'node:fs';
import {randomBytes} from 'node:crypto';
import {spawn} from 'node:child_process';
const file='.env.local';
if(existsSync(file))process.loadEnvFile(file);
if(!process.env.SIMULATION_SERVICE_TOKEN){
  const token=randomBytes(32).toString('hex');
  const separator=existsSync(file)&&!readFileSync(file,'utf8').endsWith('\n')?'\n':'';
  appendFileSync(file,`${separator}SIMULATION_SERVICE_TOKEN=${token}\n`,{mode:0o600});
  chmodSync(file,0o600);process.env.SIMULATION_SERVICE_TOKEN=token;
  console.log('Created a local simulation-service secret in ignored .env.local. Existing settings and data were preserved.');
}
if(process.env.SIMULATION_SERVICE_TOKEN.length<32)throw Error('SIMULATION_SERVICE_TOKEN must contain at least 32 characters. Correct the existing configuration; it will not be overwritten.');
process.env.SIMULATION_SERVICE_URL||='http://127.0.0.1:8000';
process.env.NEXT_DIST_DIR||='.next-local';
const children=[];let stopping=false;
const stop=()=>{if(stopping)return;stopping=true;for(const child of children)if(!child.killed)child.kill('SIGTERM');};
const launch=(cmd,args)=>{const child=spawn(cmd,args,{stdio:'inherit',env:process.env});children.push(child);child.on('error',()=>{console.error('A local service could not start. Install Node and the Python requirements first.');stop();process.exitCode=1;});child.on('exit',code=>{if(!stopping){stop();process.exitCode=code||0;}});return child;};
launch(process.env.PYTHON_BIN||'python',['-m','uvicorn','modeling.service:app','--host','127.0.0.1','--port','8000','--workers','1']);
launch(process.execPath,['node_modules/next/dist/bin/next','dev','--hostname','127.0.0.1']);
process.on('SIGINT',stop);process.on('SIGTERM',stop);
