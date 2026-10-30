import {requireUser,rateLimit,errorResponse} from '@/lib/auth';
import {getDb} from '@/lib/db';
import {handleQuant,QuantStorage} from '@/lib/quant';
export const runtime='nodejs';export const maxDuration=300;
async function route(request:Request){try{const user=await requireUser(request);if(request.method==='POST')rateLimit('quant:'+user.id,6,3600000);
 const decode=(row:any)=>row?{id:row.id,kind:row.kind,status:row.status,data:JSON.parse(row.data),result:row.result?JSON.parse(row.result):null,error:row.error,createdAt:row.created_at,updatedAt:row.updated_at}:null;
 const storage:QuantStorage={save:async job=>{getDb().prepare('INSERT INTO simulation_jobs(id,user_id,kind,status,data,result,error,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,result=excluded.result,error=excluded.error,updated_at=excluded.updated_at WHERE simulation_jobs.user_id=excluded.user_id').run(job.id,user.id,job.kind,job.status,JSON.stringify(job.data),job.result?JSON.stringify(job.result):null,job.error??null,job.createdAt,job.updatedAt);},list:async()=>getDb().prepare("SELECT * FROM simulation_jobs WHERE user_id=? AND kind IN ('benchmark','predict','trace') ORDER BY created_at DESC LIMIT 50").all(user.id).map(row=>decode(row)!),get:async id=>decode(getDb().prepare('SELECT * FROM simulation_jobs WHERE user_id=? AND id=?').get(user.id,id))};
 return await handleQuant(request,user.id,storage);
 }catch(e){return errorResponse(e);}}
export const GET=route;export const POST=route;
