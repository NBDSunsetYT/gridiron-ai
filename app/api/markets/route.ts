import { NextResponse } from 'next/server';
import { z } from 'zod';
import { randomUUID } from 'node:crypto';
import { getDb } from '@/lib/db';
import { requireUser, guardMutation, errorResponse,rateLimit,readJsonObject } from '@/lib/auth';
import { Market, TheOddsApi, providerStatuses, ProviderError } from '@/lib/providers';
import { distribution } from '@/lib/model';
import { readMarkets } from '@/lib/markets';
export const runtime='nodejs';
export async function GET(request:Request) {
  try {const user=await requireUser(request);const markets=readMarkets(user.id);return NextResponse.json({markets,providers:providerStatuses(markets)},{headers:{'Cache-Control':'private, no-store'}});} catch(e){return errorResponse(e);}
}
const manual=z.object({event:z.string().min(3).max(180),selection:z.string().min(1).max(140),market:z.string().min(2).max(100),line:z.number().finite().optional(),odds:z.number().finite().refine(v=>Math.abs(v)>=100&&Math.abs(v)<=100000,'Invalid American odds'),sportsbook:z.enum(['DraftKings','Hard Rock','Other']),observedAt:z.string().datetime().optional(),sourceUrl:z.string().url().max(500).optional(),provenance:z.string().max(1000).optional(),samples:z.array(z.number().finite()).min(20).max(10000).optional(),direction:z.enum(['over','under']).optional()});
export async function POST(request:Request) {
  try {
    guardMutation(request);const user=await requireUser(request);
    rateLimit(`markets:${user.id}`,20,60000);
    const body=await readJsonObject(request);let markets:Market[];
    if(body.action==='refresh') markets=await new TheOddsApi(process.env.ODDS_API_KEY??'').fetchMarkets();
    else {
      const items=z.array(manual).min(1).max(500).parse(body.markets??[body]);
      markets=items.map(m=>{
        if(m.observedAt&&Date.parse(m.observedAt)>Date.now()+60000)throw new Error('Observation time cannot be in the future.');
        if(m.samples&&(!m.provenance||m.line===undefined||!m.direction))throw new Error('Samples require provenance, a line and direction.');
        return {...m,id:randomUUID(),source:'manual',observedAt:m.observedAt??new Date().toISOString(),sampleSize:m.samples?.length??0,model:m.samples?distribution(m.samples,m.line!,m.direction!,m.odds):undefined} as Market;
      });
    }
    const insert=getDb().prepare('INSERT INTO markets(id,user_id,data,created_at) VALUES(?,?,?,?)');
    getDb().transaction(()=>{for(const m of markets)insert.run(m.id,user.id,JSON.stringify(m),new Date().toISOString());})();
    return NextResponse.json({markets:readMarkets(user.id),imported:markets.length,message:markets.length?'Snapshots saved with source and observation time.':'No supported DraftKings or Hard Rock markets were supplied. No prices were invented.'});
  } catch(e) {if(e instanceof ProviderError)return NextResponse.json({error:e.message},{status:e.status});if(e instanceof z.ZodError)return NextResponse.json({error:e.issues.map(i=>i.message).join('; ')},{status:400});if(e instanceof Error&&!('status' in e))return NextResponse.json({error:e.message},{status:400});return errorResponse(e);}
}
