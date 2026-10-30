import {createHash,randomBytes} from 'node:crypto';
import {ApiError,errorResponse,guardMutation,requestOrigin} from '../auth';
import {selectedBackend} from '../backend';
import {cloudClient,cloudConfiguration,cloudFetch,cookieValue,ensureProfile,finishCloud,setCloudSession,type CloudContext} from './context';

export const APP_PKCE_COOKIE='gridiron_app_pkce';
type Providers={emailPassword:boolean;apple:boolean;status:'available'|'unavailable';checkedAt:string};
let providerCache:{origin:string;expires:number;value:Providers}|null=null;
const attempts=new Map<string,{count:number;until:number}>();

function appCookie(request:Request,value:string,seconds:number){
 const secure=new URL(requestOrigin(request)).protocol==='https:';
 return `${APP_PKCE_COOKIE}=${encodeURIComponent(value)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${seconds}${secure?'; Secure':''}`;
}
function pkce(){const verifier=randomBytes(32).toString('base64url');return{verifier,challenge:createHash('sha256').update(verifier).digest('base64url')};}
function appOrigin(request:Request){
 const origin=requestOrigin(request),url=new URL(origin);
 if(url.protocol!=='https:'&&!['localhost','127.0.0.1'].includes(url.hostname))throw new ApiError('Secure app sign-in is temporarily unavailable.',503);
 return origin;
}
function limit(request:Request){
 const now=Date.now();for(const[key,value]of attempts)if(value.until<now)attempts.delete(key);
 const key=createHash('sha256').update(request.headers.get('x-forwarded-for')?.split(',')[0]?.trim()??'local').digest('hex'),previous=attempts.get(key);
 if((previous?.count??0)>=10||attempts.size>=10000)throw new ApiError('Too many sign-in attempts. Please try again later.',429);
 attempts.set(key,{count:(previous?.count??0)+1,until:previous?.until??now+15*60000});
}
function cloudSelected(request:Request){return selectedBackend(cookieValue(request,'gridiron_backend'))==='supabase';}

/** Only public provider capabilities leave the server, never provider secrets. */
export async function appAuthProviders(request:Request):Promise<Providers>{
 if(!cloudSelected(request))return{emailPassword:true,apple:false,status:'available',checkedAt:new Date().toISOString()};
 let config:ReturnType<typeof cloudConfiguration>;try{config=cloudConfiguration();}catch{return{emailPassword:false,apple:false,status:'unavailable',checkedAt:new Date().toISOString()};}
 if(providerCache?.origin===config.url&&providerCache.expires>Date.now())return providerCache.value;
 let result:Providers={emailPassword:false,apple:false,status:'unavailable',checkedAt:new Date().toISOString()};
 try{
  const response=await cloudFetch(new URL('/auth/v1/settings',config.url),{headers:{apikey:config.key},cache:'no-store',signal:AbortSignal.timeout(10000)});
  if(response.ok){const settings=await response.json();result={emailPassword:settings.external?.email===true,apple:settings.external?.apple===true,status:'available',checkedAt:new Date().toISOString()};}
 }catch{/* The UI does not advertise a provider that could not be verified. */}
 providerCache={origin:config.url,expires:Date.now()+(result.status==='available'?60000:10000),value:result};return result;
}
export async function providersResponse(request:Request){return Response.json(await appAuthProviders(request),{headers:{'Cache-Control':'private, no-store'}});}

/** The browser starts on GRIDIRON AI. The identity provider handles consent;
 * a short-lived HttpOnly verifier binds its return to this browser. */
export async function startAppleSignIn(request:Request){
 try{
  guardMutation(request);const origin=appOrigin(request);
  if(request.headers.get('origin')!==origin)throw new ApiError('Start sign-in from GRIDIRON AI.',403);
  if(!cloudSelected(request)||(await appAuthProviders(request)).apple!==true)throw new ApiError('Sign in with Apple is not available. Use your GRIDIRON AI email and password.',503);
  limit(request);const config=cloudConfiguration(),{verifier,challenge}=pkce(),url=new URL('/auth/v1/authorize',config.url);
  url.searchParams.set('provider','apple');url.searchParams.set('redirect_to',origin);url.searchParams.set('code_challenge',challenge);url.searchParams.set('code_challenge_method','s256');
  return Response.json({url:url.href},{headers:{'Cache-Control':'private, no-store','Set-Cookie':appCookie(request,verifier,600)}});
 }catch(error){const response=errorResponse(error);response.headers.set('Cache-Control','private, no-store');return response;}
}

/** Registration remains a normal app operation. Email confirmation is kept;
 * PKCE lets its app return establish secure server cookies without URL tokens. */
export async function registerCloudAccount(ctx:CloudContext,values:{email:string;password:string}){
 const config=cloudConfiguration(),origin=appOrigin(ctx.request),{verifier,challenge}=pkce(),url=new URL('/auth/v1/signup',config.url);url.searchParams.set('redirect_to',origin);
 let response:Response;
 try{response=await cloudFetch(url,{method:'POST',headers:{apikey:config.key,'Content-Type':'application/json'},body:JSON.stringify({...values,code_challenge:challenge,code_challenge_method:'s256'}),signal:AbortSignal.timeout(15000),cache:'no-store'});}catch{return{data:{session:null,user:null},error:{status:503,message:'Account creation is temporarily unavailable.'}};}
 let value:any;try{value=await response.json();}catch{return{data:{session:null,user:null},error:{status:503,message:'Account creation could not be verified.'}};}
 if(!response.ok)return{data:{session:null,user:null},error:{status:response.status,message:response.status===429?'Please wait before requesting another confirmation email.':'Unable to create an account with these details. Please try again.'}};
 const session=typeof value.access_token==='string'&&typeof value.refresh_token==='string'?value:null;
 ctx.cookies.push(appCookie(ctx.request,session?'':verifier,session?0:3600));
 return{data:{session,user:value.user??value},error:null};
}

export async function completeAppSignIn(request:Request){
 let response:Response;
 const origin=appOrigin(request),failure=()=>new Response(null,{status:303,headers:{Location:new URL('/auth/error',origin).href,'Cache-Control':'private, no-store','Referrer-Policy':'no-referrer'}});
 try{
  const code=new URL(request.url).searchParams.get('code'),verifier=cookieValue(request,APP_PKCE_COOKIE);
  if(!cloudSelected(request)||!code||code.length<16||code.length>2048||/[\u0000-\u0020]/.test(code)||!verifier||!/^[A-Za-z0-9_-]{43}$/.test(verifier))throw new ApiError('Sign-in could not be completed.');
  const config=cloudConfiguration(),tokenResponse=await cloudFetch(new URL('/auth/v1/token?grant_type=pkce',config.url),{method:'POST',headers:{apikey:config.key,'Content-Type':'application/json'},body:JSON.stringify({auth_code:code,code_verifier:verifier}),signal:AbortSignal.timeout(15000),cache:'no-store'});
  if(!tokenResponse.ok)throw new ApiError('Sign-in could not be completed.');
  const session=await tokenResponse.json();if(typeof session.access_token!=='string'||typeof session.refresh_token!=='string')throw new ApiError('Sign-in could not be verified.');
  const client=cloudClient(session.access_token),verified=await client.auth.getUser(session.access_token);
  if(verified.error||!verified.data.user)throw new ApiError('Sign-in could not be verified.');
  const ctx:CloudContext={request,client,user:verified.data.user,accessToken:session.access_token,cookies:[]};
  await ensureProfile(ctx);setCloudSession(ctx,session);
  response=finishCloud(ctx,new Response(null,{status:303,headers:{Location:new URL('/#wallet',origin).href,'Referrer-Policy':'no-referrer'}}));
 }catch{response=failure();}
 response.headers.append('Set-Cookie',appCookie(request,'',0));return response;
}
