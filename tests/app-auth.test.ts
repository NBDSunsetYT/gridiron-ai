import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {createHash} from 'node:crypto';
import {NextRequest} from 'next/server';
const sdk=vi.hoisted(()=>({create:vi.fn(),getUser:vi.fn(),profileOwner:vi.fn()}));
vi.mock('@supabase/supabase-js',()=>({createClient:sdk.create}));
import {APP_PKCE_COOKIE,appAuthProviders,completeAppSignIn,providersResponse,registerCloudAccount,startAppleSignIn} from '../lib/cloud/app-auth';
import {middleware} from '../middleware';
let index=0,upstream:ReturnType<typeof vi.fn>;
const origin='https://gridiron.example.test';
const request=(path='/api/auth/apple',options:RequestInit={})=>new Request(origin+path,options);
const post=(originHeader=origin)=>request('/api/auth/apple',{method:'POST',headers:{origin:originHeader,'Content-Type':'application/json'},body:'{}'});
beforeEach(()=>{
 vi.stubEnv('APP_URL',origin);vi.stubEnv('APP_ORIGIN','');vi.stubEnv('GRIDIRON_CLOUD_ONLY','1');vi.stubEnv('SUPABASE_URL',`https://auth-${index++}.example.test`);vi.stubEnv('SUPABASE_PUBLISHABLE_KEY','sb_publishable_SYNTHETIC_AUTH_TEST');
 sdk.getUser.mockReset();sdk.create.mockReset();sdk.profileOwner.mockReset();
 sdk.create.mockImplementation(()=>({auth:{getUser:sdk.getUser},from:()=>({select:()=>({eq:(_key:string,id:string)=>{sdk.profileOwner(id);return{maybeSingle:async()=>({data:{user_id:id},error:null})};}})})}));
 upstream=vi.fn();vi.stubGlobal('fetch',upstream);
});
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
describe('GRIDIRON app identity without a developer dashboard',()=>{
 it('advertises only actual enabled providers, omitting backend configuration and secrets',async()=>{
  upstream.mockResolvedValue(Response.json({external:{email:true,apple:false},client_secret:'SYNTHETIC-DO-NOT-RETURN',site_url:'https://dashboard.example.test'}));
  const response=await providersResponse(request('/api/auth/providers')),value=await response.json();
  expect(value).toMatchObject({emailPassword:true,apple:false,status:'available'});expect(JSON.stringify(value)).not.toMatch(/secret|site_url|dashboard|publishable/);expect(response.headers.get('cache-control')).toBe('private, no-store');
 });
 it('fails closed when Apple is not configured and creates no verifier or account',async()=>{
  upstream.mockResolvedValue(Response.json({external:{email:true,apple:false}}));const response=await startAppleSignIn(post());
  expect(response.status).toBe(503);expect(response.headers.get('set-cookie')).toBeNull();expect((await response.json()).error).toMatch(/email and password/);expect(sdk.getUser).not.toHaveBeenCalled();
 });
 it('creates a short-lived server-only PKCE verifier and an app-origin Apple return',async()=>{
  upstream.mockResolvedValue(Response.json({external:{email:true,apple:true}}));const response=await startAppleSignIn(post()),value=await response.json(),url=new URL(value.url),cookie=response.headers.get('set-cookie')!;
  expect(response.status).toBe(200);expect(url.origin).toBe(process.env.SUPABASE_URL);expect(url.pathname).toBe('/auth/v1/authorize');expect(url.searchParams.get('provider')).toBe('apple');expect(url.searchParams.get('redirect_to')).toBe(origin);expect(url.searchParams.get('code_challenge_method')).toBe('s256');
  const saved=decodeURIComponent(cookie.split(';')[0].split('=')[1]);expect(saved).toMatch(/^[A-Za-z0-9_-]{43}$/);expect(url.searchParams.get('code_challenge')).toBe(createHash('sha256').update(saved).digest('base64url'));
  expect(cookie).toContain('HttpOnly');expect(cookie).toContain('Secure');expect(cookie).toContain('SameSite=Lax');expect(cookie).toContain('Max-Age=600');expect(value).not.toHaveProperty('verifier');
 });
 it('rejects cross-origin and origin-less Apple starts before contacting an identity provider',async()=>{
  expect((await startAppleSignIn(post('https://attacker.example.test'))).status).toBe(403);
  expect((await startAppleSignIn(request('/api/auth/apple',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}))).status).toBe(403);expect(upstream).not.toHaveBeenCalled();
 });
 it('retains local app password sign-in without selecting a cloud provider or leaking legacy records',async()=>{
  vi.stubEnv('GRIDIRON_CLOUD_ONLY','0');vi.stubEnv('DATA_BACKEND','sqlite');expect(await appAuthProviders(request('/api/auth/providers'))).toMatchObject({emailPassword:true,apple:false});expect(upstream).not.toHaveBeenCalled();
 });
 it('keeps public research and auth capabilities out of private rewrites while retaining private isolation',()=>{
  for(const path of ['/api/nfl','/api/nfl/games/123','/api/cfb','/api/cfb/games/123','/api/nfl/sportsbook-reference','/api/auth/providers','/api/auth/apple'])expect(middleware(new NextRequest(origin+path)).headers.get('x-middleware-rewrite')).toBeNull();
  for(const path of ['/api/ledger','/api/conversations','/api/auth'])expect(middleware(new NextRequest(origin+path)).headers.get('x-middleware-rewrite')).toBe(origin+'/api/cloud/'+path.slice('/api/'.length));
 });
 it('requires a valid HttpOnly verifier before attempting a callback exchange',async()=>{
  for(const cookie of ['',`${APP_PKCE_COOKIE}=short`,`${APP_PKCE_COOKIE}=${'A'.repeat(43)}`]){
   const path=cookie.endsWith('A'.repeat(43))?'/auth/callback':'/auth/callback?code=0123456789abcdef';const response=await completeAppSignIn(request(path,{headers:{cookie}}));
   expect(response.status).toBe(303);expect(response.headers.get('location')).toBe(origin+'/auth/error');expect(response.headers.get('set-cookie')).toContain('Max-Age=0');
  }
  expect(upstream).not.toHaveBeenCalled();
 });
 it('independently verifies the exchanged account and sets private cookies without tokens in URLs or bodies',async()=>{
  const localVerifier='A'.repeat(43);upstream.mockResolvedValue(Response.json({access_token:'SYNTHETIC_VERIFIED_ACCESS',refresh_token:'SYNTHETIC_REFRESH',expires_in:900}));sdk.getUser.mockResolvedValue({data:{user:{id:'owner-verified',email:'qa@example.test'}},error:null});
  const response=await completeAppSignIn(request('/auth/callback?code=0123456789abcdef&next=https://attacker.example.test&code_verifier=attacker',{headers:{cookie:`${APP_PKCE_COOKIE}=${localVerifier}`}}));
  expect(JSON.parse(upstream.mock.calls[0][1].body)).toEqual({auth_code:'0123456789abcdef',code_verifier:localVerifier});expect(sdk.getUser).toHaveBeenCalledWith('SYNTHETIC_VERIFIED_ACCESS');expect(sdk.profileOwner).toHaveBeenCalledWith('owner-verified');
  expect(response.status).toBe(303);expect(response.headers.get('location')).toBe(origin+'/#wallet');expect(response.headers.get('location')).not.toContain('SYNTHETIC');expect(await response.text()).toBe('');expect(response.headers.get('referrer-policy')).toBe('no-referrer');
  const cookies=response.headers.get('set-cookie')!;expect(cookies).toContain('gridiron_sb_access=SYNTHETIC_VERIFIED_ACCESS');expect(cookies).toContain('gridiron_sb_refresh=SYNTHETIC_REFRESH');expect(cookies).toContain('HttpOnly');expect(cookies).toContain('Secure');expect(cookies).toContain(`${APP_PKCE_COOKIE}=;`);
 });
 it('never establishes identity from an unverified token response and preserves any prior app session',async()=>{
  upstream.mockResolvedValue(Response.json({access_token:'SYNTHETIC_UNVERIFIED',refresh_token:'SYNTHETIC_REFRESH'}));sdk.getUser.mockResolvedValue({data:{user:null},error:{status:401}});
  const response=await completeAppSignIn(request('/auth/callback?code=0123456789abcdef',{headers:{cookie:`${APP_PKCE_COOKIE}=${'A'.repeat(43)}; gridiron_sb_access=prior-owned-session`}}));
  expect(response.headers.get('location')).toBe(origin+'/auth/error');expect(response.headers.get('set-cookie')).not.toContain('gridiron_sb_access');expect(sdk.profileOwner).not.toHaveBeenCalled();
 });
 it('keeps email confirmation and requests PKCE rather than exposing access tokens in an email return',async()=>{
  upstream.mockResolvedValue(Response.json({id:'new-account',email:'qa@example.test'}));const ctx:any={request:request('/api/cloud/auth'),cookies:[]};const result=await registerCloudAccount(ctx,{email:'qa@example.test',password:'SYNTHETIC-long-password'}),sent=upstream.mock.calls[0];
  expect(new URL(sent[0]).searchParams.get('redirect_to')).toBe(origin);expect(JSON.parse(sent[1].body)).toMatchObject({email:'qa@example.test',code_challenge_method:'s256'});expect(JSON.parse(sent[1].body).code_challenge).toMatch(/^[A-Za-z0-9_-]{43}$/);
  expect(result.data.session).toBeNull();expect(ctx.cookies[0]).toContain('HttpOnly');expect(ctx.cookies[0]).toContain('Max-Age=3600');
 });
 it('returns a bounded app error on provider failure without inventing a new session or echoing provider internals',async()=>{
  upstream.mockResolvedValue(Response.json({message:'PRIVATE AUTH PROVIDER DETAIL'},{status:429}));const ctx:any={request:request('/api/cloud/auth'),cookies:[]};const result=await registerCloudAccount(ctx,{email:'qa@example.test',password:'SYNTHETIC-long-password'});
  expect(result.error?.status).toBe(429);expect(JSON.stringify(result)).not.toContain('PRIVATE AUTH PROVIDER DETAIL');expect(ctx.cookies).toEqual([]);expect(result.data.session).toBeNull();
 });
});
