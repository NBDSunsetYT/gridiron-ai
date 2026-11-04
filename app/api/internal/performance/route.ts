import {timingSafeEqual} from 'node:crypto';
import {performanceSnapshot} from '@/lib/performance/metrics';
import {computeOperation} from '@/lib/compute/queue';
export const dynamic='force-dynamic';
export async function GET(request:Request){const secret=process.env.GRIDIRON_PUBLIC_INGEST_TOKEN,actual=request.headers.get('authorization')??'',expected='Bearer '+secret;if(!secret||secret.length<40||Buffer.byteLength(actual)!==Buffer.byteLength(expected)||!timingSafeEqual(Buffer.from(actual),Buffer.from(expected)))return Response.json({error:'Operator authorization required.'},{status:401,headers:{'Cache-Control':'private, no-store'}});return Response.json({...performanceSnapshot(),compute:await computeOperation({action:"status"}).catch(()=>({status:"unavailable"}))},{headers:{'Cache-Control':'private, no-store'}});}
