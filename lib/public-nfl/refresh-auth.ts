import {createHash,createHmac,timingSafeEqual} from 'node:crypto';
import {sharedWrite} from './store';
/** The managed scheduler's HTTP queue may be readable to database operators.
 * Only a short-lived, one-use request MAC belongs in that queue, never its key. */
export async function signedRefreshAuthorized(request:Request){
 if(request.method!=='POST'||new URL(request.url).pathname!=='/api/nfl/refresh')return false;
 const timestamp=request.headers.get('x-gridiron-timestamp')||'',nonce=request.headers.get('x-gridiron-nonce')||'',signature=request.headers.get('x-gridiron-signature')||'',secret=process.env.GRIDIRON_PUBLIC_INGEST_TOKEN;
 if(!secret||secret.length<40||!/^\d{13}$/.test(timestamp)||!/^[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i.test(nonce)||!/^[a-f0-9]{64}$/.test(signature)||Math.abs(Date.now()-Number(timestamp))>60000)return false;
 const expected=createHmac('sha256',secret).update(`GRIDIRON-REFRESH-V1\n${timestamp}\n${nonce}\nPOST\n/api/nfl/refresh`).digest(),actual=Buffer.from(signature,'hex');
 if(expected.length!==actual.length||!timingSafeEqual(expected,actual))return false;
 const key=createHash('sha256').update('cron:'+nonce).digest('hex'),replay=await sharedWrite({action:'rate_limit',key,limit:1,windowMs:120000});
 return replay?.allowed===true;
}
