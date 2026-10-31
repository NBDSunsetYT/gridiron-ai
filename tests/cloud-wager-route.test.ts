/** Handler contract tests with an already-authenticated SYNTHETIC context.
 * Actual SQL ownership/RLS is separately verified by verify-wallet-sport.mjs. */
import {beforeEach,describe,expect,it,vi} from 'vitest';
const state=vi.hoisted(()=>({context:vi.fn(),rpc:vi.fn(),profile:vi.fn(),rate:vi.fn()}));
vi.mock('../lib/cloud/context',async original=>({...await original<typeof import('../lib/cloud/context')>(),cloudContext:state.context,rpc:state.rpc,ensureProfile:state.profile,cloudRateLimit:state.rate}));
import {handleCloudRequest} from '../lib/cloud/handler';
const A='10000000-0000-4000-8000-000000000081',B='10000000-0000-4000-8000-000000000082';
const rows=[{id:'SYNTHETIC-A',userId:A,sport:'NFL',stakeCents:1000},{id:'SYNTHETIC-B',userId:B,sport:'CFB',stakeCents:2000}];
function request(method='GET',owner:string|null=A,body?:unknown,extra:Record<string,string>={}){return new Request('https://example.invalid/api/bets?userId='+B,{method,headers:{...(owner?{'x-synthetic-established-owner':owner}:{}),...(method!=='GET'?{'content-type':'application/json'}:{}),...extra},...body===undefined?{}:{body:JSON.stringify(body)}});}
beforeEach(()=>{
 vi.clearAllMocks();state.context.mockImplementation(async(request:Request)=>{const id=request.headers.get('x-synthetic-established-owner');return{request,user:id===A||id===B?{id,email:'SYNTHETIC@example.test'}:null,client:{},accessToken:null,cookies:[]};});state.profile.mockResolvedValue(undefined);state.rate.mockResolvedValue(undefined);
 state.rpc.mockImplementation(async(ctx:any,name:string,payload?:any)=>name==='gridiron_ledger'?{bets:rows.filter(row=>row.userId===ctx.user.id)}:{id:'SYNTHETIC-NEW',sport:payload.sport});
});
describe('Authenticated cloud wager method parity',()=>{
 it('GET returns only the established owner’s wagers and cannot select another owner by query',async()=>{
  for(const owner of[A,B]){const response=await handleCloudRequest(request('GET',owner),['bets']);expect(response.status).toBe(200);expect(await response.json()).toEqual({bets:rows.filter(row=>row.userId===owner)});expect(response.headers.get('cache-control')).toContain('no-store');}
  expect(state.rpc.mock.calls.every((call:any[])=>call[1]==='gridiron_ledger'&&call.length===2)).toBe(true);
 });
 it('requires private app authentication before any ledger or profile operation',async()=>{const response=await handleCloudRequest(request('GET',null),['bets']);expect(response.status).toBe(401);expect(state.rpc).not.toHaveBeenCalled();expect(state.profile).not.toHaveBeenCalled();});
 it.each(['PUT','PATCH','DELETE'])('rejects unsupported %s without dispatching financial operations',async method=>{for(const requestValue of[request(method,A,{action:'place',userId:B}),new Request('https://example.invalid/api/bets',{method,headers:{'x-synthetic-established-owner':A}})]){const response=await handleCloudRequest(requestValue,['bets']);expect(response.status).toBe(405);expect(response.headers.get('Allow')).toBe('GET, POST');}expect(state.rpc).not.toHaveBeenCalled();});
 it('retains same-origin and JSON protections on the actual POST path',async()=>{
  const response=await handleCloudRequest(request('POST',A,{action:'place'},{origin:'https://outside.example.invalid'}),['bets']);expect(response.status).toBe(403);expect(state.rpc).not.toHaveBeenCalled();
  const json=await handleCloudRequest(request('POST',A,{action:'place'},{'content-type':'text/plain'}),['bets']);expect(json.status).toBe(415);expect(state.rpc).not.toHaveBeenCalled();
 });
 it('validates sport before dispatch and preserves a valid recorded sport without changing stake or prediction',async()=>{
  const payload={action:'place',sport:'CFB',sportsbook:'DraftKings',event:'SYNTHETIC event',market:'Moneyline',selection:'SYNTHETIC YES',stake:'10.00',odds:-110,prediction:{modelVersion:'SYNTHETIC-ORIGINAL',probability:0.6}};
  expect((await handleCloudRequest(request('POST',A,{...payload,sport:'NFL '}),['bets'])).status).toBe(400);expect(state.rpc).not.toHaveBeenCalled();
  const response=await handleCloudRequest(request('POST',A,payload),['bets']);expect(response.status).toBe(201);expect(await response.json()).toMatchObject({sport:'CFB'});expect(state.rpc).toHaveBeenCalledTimes(1);expect(state.rpc.mock.calls[0][0].user.id).toBe(A);expect(state.rpc.mock.calls[0].slice(1)).toEqual(['gridiron_place_bet',payload]);
 });
});
