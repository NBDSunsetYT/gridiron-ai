import { NextResponse } from 'next/server';
import { requireUser,guardMutation,errorResponse,rateLimit,readJsonObject } from '@/lib/auth';
import { distribution,parlay } from '@/lib/model';
export const runtime='nodejs';
export async function POST(request:Request) {
  try {
    guardMutation(request);const user=await requireUser(request);rateLimit(`model:${user.id}`,30,60000);const input=await readJsonObject(request);
    if(input.action==='parlay') return NextResponse.json(parlay({probabilities:input.probabilities,odds:input.odds,independenceAssumed:input.independenceAssumed,jointSamples:input.jointSamples}));
    if(typeof input.provenance!=='string'||input.provenance.trim().length<3) return NextResponse.json({error:'Describe the source of the submitted observations.'},{status:400});
    return NextResponse.json({...distribution(input.samples,input.threshold,input.direction,input.odds),provenance:input.provenance,createdAt:new Date().toISOString()});
  }catch(e){if(e instanceof Error&&!('status' in e))return NextResponse.json({error:e.message},{status:400});return errorResponse(e);}
}
