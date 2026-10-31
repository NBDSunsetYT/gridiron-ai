import {ApiError,errorResponse,guardMutation,readJsonObject} from '../auth';
import {publicRateLimit} from '../public-nfl/store';
import {sportsbookReferenceDashboard,analyzeNflSportsbookReference} from './service';
import {sportsDataBridgeConfiguration} from './bridge';
import type {SportsbookReferenceFilters} from './types';
const json=(value:unknown,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
function filters(request:Request):SportsbookReferenceFilters{const q=new URL(request.url).searchParams,filter:SportsbookReferenceFilters={};if(q.has('cursor'))filter.cursor=Number(q.get('cursor'));if(q.has('limit'))filter.limit=Number(q.get('limit'));for(const field of['vendor','statistic']as const)if(q.has(field)){const value=q.get(field)!;if(!/^[a-z_]{1,80}$/.test(value))throw new ApiError('Choose a supported reference-data filter.');filter[field]=value;}if(q.has('scope')){const scope=q.get('scope');if(scope!=='all'&&scope!=='player'&&scope!=='game')throw new ApiError('Choose all, player or game sportsbook references.');filter.scope=scope;}return filter;}
export async function handleSportsbookReference(request:Request,path:string[]=[]){try{
 if(!path.length&&request.method==='GET')return json(await sportsbookReferenceDashboard(filters(request)));
 if((!path.length||path.length===1&&path[0]==='analyze')&&request.method==='POST'){
  guardMutation(request);const input=await readJsonObject(request);if(Object.keys(input).some(k=>k!=='gameId')||input.gameId!==undefined&&(typeof input.gameId!=='string'||!/^\d{4}_\d{2,3}_[A-Z0-9]{2,3}_[A-Z0-9]{2,3}$/.test(input.gameId)))throw new ApiError('Choose a verified NFL game; client statistics, provider credentials and arbitrary URLs are not accepted.');
  const filter=filters(request);if(sportsDataBridgeConfiguration())return json(await sportsbookReferenceDashboard(filter));await publicRateLimit(request,'nfl-sportsbook-reference',6,3600000);return json(await analyzeNflSportsbookReference(input,filter),202);
 }
 throw new ApiError('NFL sportsbook reference route not found.',404);
}catch(error){return errorResponse(error);}}
