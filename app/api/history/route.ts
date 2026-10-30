import {NextResponse} from 'next/server';
import {requireUser,errorResponse} from '@/lib/auth';
import {contractHistory} from '@/lib/contracts';
import {readInjuries} from '@/lib/injuries';
import {getDb} from '@/lib/db';
export async function GET(request:Request){try{const u=await requireUser(request);const contracts=contractHistory(u.id);const notifications=(getDb().prepare('SELECT data FROM notification_history WHERE user_id=? ORDER BY created_at DESC LIMIT 200').all(u.id) as {data:string}[]).map(r=>JSON.parse(r.data));return NextResponse.json({...contracts,injuryHistory:readInjuries(u.id).history,notifications},{headers:{'Cache-Control':'private,no-store'}});}catch(e){return errorResponse(e);}}
