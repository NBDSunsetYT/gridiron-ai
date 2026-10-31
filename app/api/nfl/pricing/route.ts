import {guardMutation,readJsonObject,errorResponse,ApiError} from '@/lib/auth';
import {currentDraftKingsFeeReference,draftKingsStandardFill} from '@/lib/draftkings-predictions-pricing';
import {publicRateLimit} from '@/lib/public-nfl/store';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export async function GET(){try{return Response.json({reference:await currentDraftKingsFeeReference(),scope:'Official standard venue fee reference; no live contract price, account eligibility or executable fill is asserted.'},{headers:{'Cache-Control':'no-store'}});}catch(error){return errorResponse(error);}}
export async function POST(request:Request){try{guardMutation(request);const body=await readJsonObject(request);if(Object.keys(body).some(key=>!['venue','pricePercent','quantity','direction'].includes(key)))throw new ApiError('Only venue, percentage price, quantity and buy/sell direction are accepted.');await publicRateLimit(request,'predictions-fee-reference',30,3600000);return Response.json(draftKingsStandardFill(body as Parameters<typeof draftKingsStandardFill>[0],await currentDraftKingsFeeReference()),{headers:{'Cache-Control':'no-store'}});}catch(error){return errorResponse(error);}}
