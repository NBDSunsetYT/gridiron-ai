/** End-to-end transport helper. A queued receipt is never a completed model. */
export async function runSavedSimulation(client,input,{pollMs=2500,deadlineMs=600000,sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms)),now=Date.now,onProgress=()=>{}}={}){
 const started=now(),submitted=await client.call('simulations',input);
 if(![200,202].includes(submitted.status))throw Error(`Simulation submission HTTP ${submitted.status}: ${safeError(submitted.data?.error)}`);
 const receipt=submitted.data;
 if(!receipt||typeof receipt.id!=='string')throw Error('Simulation did not return a saved job identifier.');
 if(submitted.status===200&&!receipt.pending){
  if(receipt.status&&receipt.status!=='completed')throw Error('Synchronous simulation returned an unfinished job.');
  return{id:receipt.id,status:'completed',result:receipt,asynchronous:false};
 }
 let previousStatus=null;
 while(now()-started<=deadlineMs){
  const response=await client.call('simulations?id='+encodeURIComponent(receipt.id));
  if([502,503,504].includes(response.status)){await sleep(pollMs);continue;}
  if(response.status!==200)throw Error(`Saved simulation read HTTP ${response.status}: ${safeError(response.data?.error)}`);
  const job=response.data?.job;
  if(!job||job.id!==receipt.id)throw Error('Saved simulation identity does not match its receipt.');
  if(job.status!==previousStatus){onProgress({id:job.id,status:job.status});previousStatus=job.status;}
  if(job.status==='completed'){
   if(job.provenanceVerified!==true)throw Error('Completed simulation is missing a verified engine receipt.');
   if(!job.result||typeof job.result!=='object')throw Error('Completed simulation has no persisted result.');
   return{id:job.id,status:'completed',result:job.result,asynchronous:true,provenanceVerified:true};
  }
  if(['failed','blocked'].includes(job.status))return{id:job.id,status:job.status,error:safeError(job.error),asynchronous:true};
  if(!['queued','running'].includes(job.status))throw Error('Saved simulation has an unrecognized status.');
  await sleep(pollMs);
 }
 throw Error(`Saved simulation ${receipt.id} exceeded the ${deadlineMs}ms verification deadline; no completion is claimed. The saved job remains available.`);
}

function safeError(value){return typeof value==='string'?value.slice(0,1500):'No provider detail available.';}

/** Read normalized source CSV without assuming quoted fields have no commas. */
export function receiverFromNormalizedCsv(csv,teams){
 const rows=parseCsv(csv);const columns=rows.shift()??[],offense=columns.indexOf('offense'),receiver=columns.indexOf('receiver_id');
 if(offense<0||receiver<0)return null;
 return rows.find(row=>teams.includes(row[offense])&&row[receiver])?.[receiver]??null;
}

function parseCsv(text){
 const rows=[];let row=[],cell='',quoted=false;
 for(let i=0;i<text.length;i++){
  const c=text[i];
  if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}
  else if(c===','&&!quoted){row.push(cell);cell='';}
  else if((c==='\r'||c==='\n')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);rows.push(row);row=[];cell='';}
  else cell+=c;
 }
 if(quoted)throw Error('Normalized CSV contains an unterminated quoted field.');
 if(cell||row.length){row.push(cell);rows.push(row);}
 return rows;
}
