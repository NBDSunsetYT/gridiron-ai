/** Operator stdin transport: keys never enter command arguments, files or output. */
import {createInterface} from 'node:readline';
import {mkdirSync,writeFileSync} from 'node:fs';
import {EnvHttpProxyAgent,setGlobalDispatcher} from 'undici';
if(process.env.HTTPS_PROXY||process.env.HTTP_PROXY)setGlobalDispatcher(new EnvHttpProxyAgent());
const receiver=createInterface({input:process.stdin});
console.log('Bridge verifier ready for private stdin configuration.');
receiver.once('line',async line=>{
 try{
  const input=JSON.parse(line),base='https://gridiron-propline-gateway.onrender.com';
  if(typeof input.token!=='string'||input.token.length<32)throw Error('Missing bridge capability');
  const probe=async(path,authenticated=true)=>{const started=Date.now(),response=await fetch(base+path,{headers:authenticated?{Authorization:'Bearer '+input.token}:{},redirect:'error',signal:AbortSignal.timeout(45000)});const data=await response.json();if(JSON.stringify(data).includes(input.token))throw Error('Credential escaped the gateway boundary');return{path,httpStatus:response.status,wallMs:Date.now()-started,data};};
  const privateMetrics=await probe('/metrics'),anonymous=await probe('/metrics',false);
  if(privateMetrics.httpStatus!==200||anonymous.httpStatus!==401)throw Error('Bridge authentication verification failed');
  const rows=[{path:'/metrics',authenticatedStatus:privateMetrics.httpStatus,unauthenticatedStatus:anonymous.httpStatus,wallMs:privateMetrics.wallMs}];
  const responses=[];
  if(input.providers===true)for(const sport of ['NFL','CFB','NBA']){
   const value=await probe('/data/props/'+sport+'?limit=50');responses.push(value);const items=value.data.items??[];
   rows.push({sport,path:value.path,httpStatus:value.httpStatus,wallMs:value.wallMs,status:value.data.status,provider:value.data.provider,items:items.length,totalResults:value.data.totalResults,categories:[...new Set(items.map(i=>i.marketType??i.market??i.stat))],sportsbooks:[...new Set(items.map(i=>i.book?.key??i.sportsbook??i.bookmaker))],marketCounts:value.data.marketCounts,bookCounts:value.data.bookCounts,quota:value.data.quota,sourceChecks:value.data.sourceChecks,diagnostic:value.data.diagnostic});
  }
  const directory='artifacts/render-migration-v24/followup';mkdirSync(directory,{recursive:true});
  writeFileSync(directory+'/bridge-verification.json',JSON.stringify(rows,null,2));
  if(responses.length)writeFileSync(directory+'/gateway-responses.json',JSON.stringify(responses),{mode:0o600});
  console.log(JSON.stringify({authenticated:true,legacyCredentialChanged:false,checks:rows}));
 }catch{console.error('Bridge verification failed. No credential was disclosed.');process.exitCode=1;}
 finally{receiver.close();}
});
