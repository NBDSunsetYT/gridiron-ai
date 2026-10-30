import {NextResponse} from 'next/server';
import {z} from 'zod';
import {requireUser,guardMutation,errorResponse,rateLimit,readJsonObject} from '@/lib/auth';
import {contractHistory,saveQuote,savePrediction,settleContract,savePaperPosition} from '@/lib/contracts';
export const runtime='nodejs';
export async function GET(request:Request){try{const u=await requireUser(request);return NextResponse.json(contractHistory(u.id),{headers:{'Cache-Control':'private,no-store'}});}catch(e){return errorResponse(e);}}
export async function POST(request:Request){try{guardMutation(request);const u=await requireUser(request);rateLimit(`contracts:${u.id}`,30,60000);const p=await readJsonObject(request);
  if(p.action==='quote')return NextResponse.json({quote:saveQuote(u.id,p)},{status:201});
  if(p.action==='predict')return NextResponse.json({prediction:savePrediction(u.id,p)},{status:201});
  if(p.action==='settle')return NextResponse.json({settlement:settleContract(u.id,p)},{status:201});
  if(p.action==='paper')return NextResponse.json({position:savePaperPosition(u.id,p)},{status:201});
  return NextResponse.json({error:'Choose quote, predict, settle or paper.'},{status:400});
}catch(e){if(e instanceof z.ZodError)return NextResponse.json({error:e.issues.map(i=>i.path.join('.')+': '+i.message).join('; ')},{status:400});return errorResponse(e);}}
