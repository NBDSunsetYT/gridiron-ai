import {guardMutation,readJsonObject,errorResponse,ApiError} from '@/lib/auth';
import {targetSchema} from '@/lib/probability/schema';
import {automaticCombination} from '@/lib/probability/automatic-combinations';
import {publicRateLimit} from '@/lib/public-nfl/store';
export const runtime='nodejs';export const dynamic='force-dynamic';export const maxDuration=300;
export async function POST(request:Request){try{guardMutation(request);const parsed=targetSchema.safeParse(await readJsonObject(request));if(!parsed.success||parsed.data.type!=='combination'||parsed.data.legs.some(l=>l.type!=='prop'))throw new ApiError('Choose two to twelve exact player-prop definitions.');await publicRateLimit(request,'automatic-combination',90,3600000);return Response.json(await automaticCombination(parsed.data),{headers:{'Cache-Control':'private, no-store'}});}catch(error){return errorResponse(error);}}
