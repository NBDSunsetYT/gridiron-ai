import {NextResponse,after} from 'next/server';
import {z} from 'zod';
import {requireUser,guardMutation,errorResponse,rateLimit,readJsonObject} from '@/lib/auth';
import {readInjuries,saveInjury} from '@/lib/injuries';
import {processSimulationJobs} from '@/lib/jobs';
export const runtime='nodejs';
export const maxDuration=300;
export async function GET(request:Request){try{const u=await requireUser(request);return NextResponse.json(readInjuries(u.id),{headers:{'Cache-Control':'private,no-store'}});}catch(e){return errorResponse(e);}}
export async function POST(request:Request){try{guardMutation(request);const u=await requireUser(request);rateLimit(`injuries:${u.id}`,30,60000);const result=saveInjury(u.id,await readJsonObject(request));if(result.resimulationRequired)after(async()=>{await processSimulationJobs(u.id,3);});return NextResponse.json(result,{status:201});}catch(e){if(e instanceof z.ZodError)return NextResponse.json({error:e.issues.map(i=>i.path.join('.')+': '+i.message).join('; ')},{status:400});return errorResponse(e);}}
