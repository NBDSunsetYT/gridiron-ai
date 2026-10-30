/** Explicit account migration. Never resets or modifies the source SQLite database/archive.
 * Secrets arrive as one JSON object on stdin, never command arguments or output.
 */
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const [, ,originArg,backupPath]=process.argv;
if(!originArg||!backupPath)throw new Error('Usage: node --import tsx scripts/migrate-cloud.ts https://your-host encrypted-backup.json < private-stdin');
const origin=new URL(originArg);
if(origin.username||origin.password||origin.protocol!=='https:'&&!['localhost','127.0.0.1'].includes(origin.hostname))throw new Error('Use an HTTPS application origin (or local development).');
const source=readFileSync(backupPath),digest=createHash('sha256').update(source).digest('hex');
const credentials=JSON.parse(readFileSync(0,'utf8')) as {email:string;password:string;backupPassword:string};
if(!credentials.email||!credentials.password||!credentials.backupPassword)throw new Error('Stdin requires email, password and backupPassword fields.');
let cookie='';
async function post(path:string,body:unknown){const response=await fetch(new URL(path,origin),{method:'POST',headers:{'Content-Type':'application/json',Origin:origin.origin,...cookie?{Cookie:cookie}:{}},body:JSON.stringify(body),signal:AbortSignal.timeout(120000)});const values=response.headers.getSetCookie();if(values.length)cookie=values.map(v=>v.split(';')[0]).join('; ');const result=await response.json();if(!response.ok)throw new Error(result.error||`Application returned HTTP ${response.status}.`);return result;}
try{
 const login=await post('/api/cloud/auth',{action:'login',email:credentials.email,password:credentials.password});
 if(!login.user)throw new Error('Confirm the Supabase account email and sign in before migration.');
 const result=await post('/api/cloud/migrate',{envelope:JSON.parse(source.toString('utf8')),password:credentials.backupPassword});
 if(createHash('sha256').update(readFileSync(backupPath)).digest('hex')!==digest)throw new Error('The source archive changed during migration. Preserve it and reconcile before proceeding.');
 console.log(JSON.stringify({status:'completed',sourcePreserved:true,migration:result.migration}));
}finally{
 credentials.password='';credentials.backupPassword='';
 if(cookie)try{await post('/api/cloud/auth',{action:'logout'});}catch{console.error('The temporary migration session could not be revoked remotely. Sign out of that account securely.');}
 cookie='';
}
