import {createClient, type SupabaseClient, type User} from '@supabase/supabase-js';
import {ApiError, requestOrigin} from '../auth';

export const ACCESS_COOKIE='gridiron_sb_access';
export const REFRESH_COOKIE='gridiron_sb_refresh';
export type CloudContext={request:Request;client:SupabaseClient;user:User|null;accessToken:string|null;cookies:string[]};
export class CloudAuthUnavailable extends ApiError{constructor(public context:CloudContext){super('Supabase could not verify the refreshed identity. Retry when authentication is available; rotated credentials were preserved securely.',503);}}
export const authUnavailable=(error:any)=>Boolean(error)&&(Number(error.status)>=500||error.status===0||/retryable|fetch|abort/i.test(String(error.name)));
export function cloudConfiguration(){
 const url=process.env.SUPABASE_URL,key=process.env.SUPABASE_PUBLISHABLE_KEY;
 if(!url||!key)throw new ApiError('Supabase is selected but SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are not configured. Local records were not used as a substitute.',503);
 const parsed=new URL(url);
 if(parsed.protocol!=='https:'&&!['localhost','127.0.0.1'].includes(parsed.hostname))throw new ApiError('Supabase must use HTTPS.',503);
 if(key.startsWith('sb_secret_'))throw new ApiError('Configure a publishable Supabase key, not a secret/service-role key.',503);
 if(!key.startsWith('sb_publishable_')){let role:string|undefined;try{role=JSON.parse(Buffer.from(key.split('.')[1]??'','base64url').toString('utf8')).role;}catch{}if(role!=='anon')throw new ApiError('The configured key is not a publishable or legacy anonymous Supabase key. Service-role credentials are prohibited in this client.',503);}
 return{url,key};
}
export function cloudClient(accessToken?:string){
 const {url,key}=cloudConfiguration();
 // SDK 2.102+ retries PostgREST POSTs by default. Do not ambiguously replay an
 // account mutation or wait indefinitely for a stalled provider upload.
 return createClient(url,key,{db:{retry:false},auth:{persistSession:false,autoRefreshToken:false,detectSessionInUrl:false},global:{headers:accessToken?{Authorization:`Bearer ${accessToken}`}:{},fetch:cloudFetch}});
}
export function cloudFetch(input:RequestInfo|URL,init?:RequestInit){
 const signals=[AbortSignal.timeout(60000),...(init?.signal?[init.signal]:[]),...(input instanceof Request?[input.signal]:[])];
 return fetch(input,{...init,signal:AbortSignal.any(signals)});
}
export function cookieValue(request:Request,name:string){
 const raw=request.headers.get('cookie')?.split(';').map(v=>v.trim()).find(v=>v.startsWith(name+'='))?.slice(name.length+1);
 if(!raw)return null;try{return decodeURIComponent(raw);}catch{return null;}
}
function cookie(request:Request,name:string,value:string,maxAge:number){
 const secure=new URL(requestOrigin(request)).protocol==='https:';
 return `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${secure?'; Secure':''}`;
}
export function setCloudSession(ctx:CloudContext,session:{access_token:string;refresh_token:string;expires_in?:number}){
 ctx.accessToken=session.access_token;
 ctx.cookies.push(cookie(ctx.request,ACCESS_COOKIE,session.access_token,Math.max(1,session.expires_in??3600)));
 ctx.cookies.push(cookie(ctx.request,REFRESH_COOKIE,session.refresh_token,30*86400));
 ctx.client=cloudClient(session.access_token);
}
export function clearCloudSession(ctx:CloudContext){
 ctx.cookies.push(cookie(ctx.request,ACCESS_COOKIE,'',0),cookie(ctx.request,REFRESH_COOKIE,'',0));ctx.accessToken=null;ctx.user=null;
}
export async function cloudContext(request:Request):Promise<CloudContext>{
 const ctx:CloudContext={request,client:cloudClient(),user:null,accessToken:cookieValue(request,ACCESS_COOKIE),cookies:[]};
 if(ctx.accessToken){
  const {data,error}=await ctx.client.auth.getUser(ctx.accessToken);
  if(!error&&data.user){ctx.user=data.user;ctx.client=cloudClient(ctx.accessToken);return ctx;}
  if(authUnavailable(error))throw new ApiError('Supabase authentication is temporarily unavailable. Your stored records have not changed.',503);
 }
 const refresh=cookieValue(request,REFRESH_COOKIE);
 if(refresh){
  const {data,error}=await ctx.client.auth.refreshSession({refresh_token:refresh});
  if(!error&&data.session){
   const verified=await ctx.client.auth.getUser(data.session.access_token);
   if(!verified.error&&verified.data.user){ctx.user=verified.data.user;setCloudSession(ctx,data.session);return ctx;}
   if(authUnavailable(verified.error)){setCloudSession(ctx,data.session);throw new CloudAuthUnavailable(ctx);}
  }
  if(authUnavailable(error))throw new ApiError('Supabase session refresh is temporarily unavailable.',503);
  clearCloudSession(ctx);
 }
 return ctx;
}
export function requireCloudUser(ctx:CloudContext){if(!ctx.user)throw new ApiError('Sign in to access your private Supabase records.',401);return ctx.user;}
export function finishCloud(ctx:CloudContext|undefined,response:Response){
 const headers=new Headers(response.headers);headers.set('Cache-Control','private, no-store');
 for(const value of ctx?.cookies??[])headers.append('Set-Cookie',value);
 return new Response(response.body,{status:response.status,headers});
}
export function forwardCloudRequest(ctx:CloudContext){
 const headers=new Headers(ctx.request.headers),jar=new Map<string,string>();
 for(const value of (headers.get('cookie')??'').split(';')){const text=value.trim(),i=text.indexOf('=');if(i>0)jar.set(text.slice(0,i),text.slice(i+1));}
 for(const value of ctx.cookies){const text=value.split(';')[0],i=text.indexOf('=');if(i>0)jar.set(text.slice(0,i),text.slice(i+1));}
 if(ctx.accessToken)jar.set(ACCESS_COOKIE,encodeURIComponent(ctx.accessToken));jar.set('gridiron_backend','supabase');headers.set('cookie',Array.from(jar,([k,v])=>k+'='+v).join('; '));
 return new Request(ctx.request,{headers});
}
export function cloudError(error:any):never{
 if(error?.code==='28000')throw new ApiError('This authenticated session was revoked. Sign in again.',401);
 if(error?.code==='P0001'&&/too many requests/i.test(String(error.message)))throw new ApiError('Too many requests. Please retry later.',429);
 if(error?.code==='23505')throw new ApiError('An immutable record or transaction reference already exists.',409);
 if(error?.code==='42501')throw new ApiError('This operation is not authorized for your account.',403);
 if(error?.code==='PGRST116')throw new ApiError('The requested owned record was not found.',404);
 if(error?.code==='P0001'||error?.code==='22023'||error?.code==='23514')throw new ApiError(String(error.message||'The database rejected invalid input.').slice(0,600),400);
 throw new ApiError('Supabase could not complete this operation. No local fallback or invented records were used.',503);
}
export async function rpc<T=any>(ctx:CloudContext,name:string,payload?:unknown):Promise<T>{
 const {data,error}=await ctx.client.rpc(name,payload===undefined?{}:{payload});if(error)cloudError(error);return data as T;
}
export async function ensureProfile(ctx:CloudContext){
 const user=requireCloudUser(ctx);const read=await ctx.client.from('profiles').select('user_id,settings').eq('user_id',user.id).maybeSingle();if(read.error)cloudError(read.error);
 if(!read.data){const result=await ctx.client.from('profiles').insert({user_id:user.id,email:user.email});if(result.error&&result.error.code!=='23505')cloudError(result.error);}
}
export async function cloudRateLimit(ctx:CloudContext,key:string,limit=60,windowMs=60000){
 const result=await rpc<any>(ctx,'gridiron_consume_rate_limit',{key,limit,windowMs});
 if(result===false||result?.allowed===false)throw new ApiError('Too many requests. Please retry later.',429);
}
