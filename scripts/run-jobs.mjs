// Run this from an operator cron or supervised background process. Never put the secret in command arguments.
const base=process.env.APP_ORIGIN||process.env.APP_URL;
const secret=process.env.CRON_SECRET;
if(!base||!secret||secret.length<32){console.error('APP_ORIGIN and a CRON_SECRET of at least32 characters are required.');process.exit(1);}
try{const response=await fetch(new URL('/api/jobs',base),{method:'POST',headers:{'Authorization':`Bearer ${secret}`,'Content-Type':'application/json'},body:'{}',signal:AbortSignal.timeout(850000)});const data=await response.json();if(!response.ok)throw Error('Worker endpoint rejected the request.');console.log(JSON.stringify({processed:data.processed,statuses:data.jobs?.map(job=>job.status)}));}catch{console.error('Research worker could not finish. Queued jobs remain durable; running leases recover after20 minutes.');process.exit(1);}
