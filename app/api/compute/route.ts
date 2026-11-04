import {computeOperation} from '@/lib/compute/queue';
export const dynamic='force-dynamic';
export const maxDuration=15;
/** Public research queue metadata only; no task payload, session, model or result. */
export async function GET(request:Request){
 const id=new URL(request.url).searchParams.get('id');if(!id||!/^[a-f0-9]{64}$/.test(id))return Response.json({error:'A research job ID is required.'},{status:400});
 try{const job=await computeOperation({action:'status',id});return Response.json(job??{error:'Research job not found.'},{status:job?200:404,headers:{'Cache-Control':'no-store','CDN-Cache-Control':'public, s-maxage=15','Vercel-CDN-Cache-Control':'public, s-maxage=15'}});}catch{return Response.json({status:'delayed',error:'Queue status is temporarily unavailable. Saved work remains intact.'},{status:503,headers:{'Retry-After':'60'}});}
}
