import {z} from 'zod';
import {ApiError,errorResponse} from '@/lib/auth';
import {publicRateLimit} from '@/lib/public-nfl/store';
import {automaticPropHistory} from '@/lib/props/history';
export const runtime='nodejs';export const dynamic='force-dynamic';export const maxDuration=300;
const schema=z.object({sport:z.enum(['NFL','CFB']),jobId:z.string().regex(/^[a-f0-9]{64}$/),eventId:z.string().min(1).max(150),playerId:z.string().regex(/^espn:\d+$/),market:z.string().min(1).max(100),threshold:z.string().min(1).max(40),side:z.enum(['Over','Under','YES','NO','Yes','No']),book:z.string().max(80),before:z.coerce.number().int().positive().optional()}).strict();
export async function GET(request:Request){try{const value=schema.safeParse(Object.fromEntries(new URL(request.url).searchParams));if(!value.success)throw new ApiError('Choose an exact saved player-prop definition.');await publicRateLimit(request,'automatic-prop-history',120,3600000);return Response.json(await automaticPropHistory(value.data),{headers:{'Cache-Control':'no-store'}});}catch(error){return errorResponse(error);}}
