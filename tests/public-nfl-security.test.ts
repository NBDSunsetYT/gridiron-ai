import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest';
import {ApiError} from '../lib/auth';
const state=vi.hoisted(()=>({user:null as null|{id:string;email:string},cookies:[] as string[],stored:false,after:[] as Array<()=>Promise<void>>}));
const service=vi.hoisted(()=>({publicDashboard:vi.fn(),publicGameDetail:vi.fn(),analyzePublicGame:vi.fn(),publicAssistant:vi.fn(),refreshPublicResearch:vi.fn()}));
const store=vi.hoisted(()=>({publicRateLimit:vi.fn(),sharedJob:vi.fn(),putCache:vi.fn()}));
const privateStore=vi.hoisted(()=>({saveRecord:vi.fn(),record:vi.fn()}));
const privateResearch=vi.hoisted(()=>({cloudCreateConversation:vi.fn(),cloudAppendMessage:vi.fn()}));
const auth=vi.hoisted(()=>({cloudContext:vi.fn()}));
vi.mock('../lib/public-nfl/service',()=>service);
vi.mock('../lib/football-refresh',()=>({refreshAdditionalFootballResearch:vi.fn(async()=>[{sport:'CFB',task:'college_sources',status:'unavailable'}])}));
vi.mock('next/server',()=>({after:(callback:()=>Promise<void>)=>state.after.push(callback)}));
vi.mock('../lib/public-nfl/store',()=>store);
vi.mock('../lib/cloud/store',()=>privateStore);
vi.mock('../lib/cloud/research',()=>privateResearch);
vi.mock('../lib/cloud/context',async importOriginal=>{const original=await importOriginal<typeof import('../lib/cloud/context')>();return{...original,cloudContext:auth.cloudContext};});
import {handlePublicNfl} from '../lib/public-nfl/handler';
const owner={id:'10000000-0000-4000-8000-000000000005',email:'SYNTHETIC-QA@example.test'},analysisId='20000000-0000-4000-8000-000000000005',gameId='2026_09_SYN_HOM';
const summary={text:'SYNTHETIC evidence-only HTTP fixture',generatedByAI:false,method:'evidence_brief',citations:[],createdAt:'2026-10-30T00:00:00Z'};
function request(path:string,body?:unknown,options:{origin?:string;contentType?:string;cookie?:string;authorization?:string}={}){return new Request('https://gridiron.example.test/api/nfl/'+path,{method:body===undefined?'GET':'POST',headers:{Origin:options.origin??'https://gridiron.example.test','Content-Type':options.contentType??'application/json',...(options.cookie?{cookie:options.cookie}:{}),...(options.authorization?{authorization:options.authorization}:{})},body:body===undefined?undefined:JSON.stringify(body)});}
beforeEach(()=>{
 vi.clearAllMocks();state.user=null;state.cookies=[];state.stored=false;state.after=[];vi.stubEnv('APP_URL','https://gridiron.example.test');vi.stubEnv('APP_ORIGIN','');vi.stubEnv('GRIDIRON_PUBLIC_INGEST_TOKEN','SYNTHETIC-INGEST-TOKEN-01234567890123456789');vi.stubEnv('CRON_SECRET','');store.putCache.mockResolvedValue(undefined);
 service.publicDashboard.mockResolvedValue({games:[],guestAccess:true});service.publicGameDetail.mockResolvedValue({game:{id:gameId},analysis:null,status:'unavailable'});service.analyzePublicGame.mockResolvedValue({game:{id:gameId},analysis:{id:analysisId,status:'queued'},status:'queued'});service.publicAssistant.mockResolvedValue({summary,analysisId,status:'evidence_brief'});service.refreshPublicResearch.mockResolvedValue({refreshed:true});store.publicRateLimit.mockResolvedValue(undefined);
 store.sharedJob.mockResolvedValue({id:analysisId,game_id:gameId,status:'completed',result:{result:{modelVersion:'SYNTHETIC-HTTP-FIXTURE',simulations:10000},summary}});
 auth.cloudContext.mockImplementation(async(req:Request)=>({request:req,user:state.user,client:{},accessToken:state.user?'SYNTHETIC-OWNER-SESSION':null,cookies:state.cookies}));
 privateStore.record.mockImplementation(async()=>{if(!state.stored)throw new ApiError('Owned record not found.',404);return{data:{}};});privateStore.saveRecord.mockImplementation(async()=>{state.stored=true;return{};});privateResearch.cloudCreateConversation.mockResolvedValue({id:'30000000-0000-4000-8000-000000000005'});privateResearch.cloudAppendMessage.mockResolvedValue({});
});
afterEach(()=>vi.unstubAllEnvs());

describe('Public NFL HTTP boundaries preserve private account security',()=>{
 it('serves shared schedule and game research without creating, checking or exposing a personal identity',async()=>{
  const response=await handlePublicNfl(request(''));expect(response.status).toBe(200);expect((await response.json()).guestAccess).toBe(true);expect(response.headers.get('Cache-Control')).toMatch(/^public/);expect(response.headers.get('Set-Cookie')).toBeNull();
  expect((await handlePublicNfl(request('games/'+gameId),['games',gameId])).status).toBe(200);expect(auth.cloudContext).not.toHaveBeenCalled();expect(privateStore.record).not.toHaveBeenCalled();expect(privateResearch.cloudCreateConversation).not.toHaveBeenCalled();
 });
 it('accepts only a trusted game reference and a supported standard simulation option, never guest statistics or credentials',async()=>{
  const ok=await handlePublicNfl(request('games/'+gameId+'/analyze',{simulations:10000}),['games',gameId,'analyze']);expect(ok.status).toBe(202);expect(service.analyzePublicGame).toHaveBeenCalledWith(gameId,10000);expect(ok.headers.get('Cache-Control')).toBe('no-store');
  service.analyzePublicGame.mockClear();for(const extra of [{csv:'SYNTHETIC malicious rows'},{model:{rows:[]}},{sourceUrl:'http://169.254.169.254/metadata'},{user_id:owner.id},{service_role:'SYNTHETIC'}]){const response=await handlePublicNfl(request('games/'+gameId+'/analyze',{simulations:10000,...extra}),['games',gameId,'analyze']);expect(response.status).toBe(400);}expect(service.analyzePublicGame).not.toHaveBeenCalled();
 });
 it('rejects cross-origin, invalid content types and rate-limited work before invoking compute',async()=>{
  expect((await handlePublicNfl(request('games/'+gameId+'/analyze',{}, {origin:'https://attacker.example.test'}),['games',gameId,'analyze'])).status).toBe(403);
  expect((await handlePublicNfl(request('games/'+gameId+'/analyze',{}, {contentType:'text/plain'}),['games',gameId,'analyze'])).status).toBe(415);
  store.publicRateLimit.mockRejectedValueOnce(new ApiError('Rate limit reached.',429));expect((await handlePublicNfl(request('games/'+gameId+'/analyze',{}),['games',gameId,'analyze'])).status).toBe(429);expect(service.analyzePublicGame).not.toHaveBeenCalled();
 });
 it('requires the dedicated server capability for scheduled refresh; an ordinary app bearer cannot refresh sources',async()=>{
  for(const authorization of [undefined,'Bearer SYNTHETIC-APP-USER-JWT','Bearer incorrect'])expect((await handlePublicNfl(request('refresh',undefined,{authorization}),['refresh'])).status).toBe(401);expect(service.refreshPublicResearch).not.toHaveBeenCalled();
  const response=await handlePublicNfl(request('refresh',undefined,{authorization:'Bearer SYNTHETIC-INGEST-TOKEN-01234567890123456789'}),['refresh']);expect(response.status).toBe(202);expect(service.refreshPublicResearch).not.toHaveBeenCalled();expect(state.after).toHaveLength(1);await state.after[0]();expect(service.refreshPublicResearch).toHaveBeenCalledOnce();expect(store.putCache).toHaveBeenCalled();
 });
 it('keeps guest explanations stateless and never writes a conversation or creates an anonymous account',async()=>{
  const response=await handlePublicNfl(request('assistant',{gameId,message:'Explain this game.'}),['assistant']);expect(response.status).toBe(200);expect((await response.json()).summary.generatedByAI).toBe(false);expect(response.headers.get('Cache-Control')).toBe('no-store');expect(auth.cloudContext).not.toHaveBeenCalled();expect(privateResearch.cloudCreateConversation).not.toHaveBeenCalled();expect(privateStore.saveRecord).not.toHaveBeenCalled();
 });
 it('saves a signed-in explanation only through the verified owner context and excludes that private ID from shared caching',async()=>{
  state.user=owner;const response=await handlePublicNfl(request('assistant',{gameId,message:'Explain my selected game.'},{cookie:'gridiron_sb_access=SYNTHETIC-OWNER-SESSION'}),['assistant']);expect(response.status).toBe(200);expect((await response.json()).historySaved).toBe(true);expect(response.headers.get('Cache-Control')).toMatch(/private.*no-store/);expect(privateResearch.cloudCreateConversation.mock.calls[0][0].user).toEqual(owner);expect(privateResearch.cloudAppendMessage).toHaveBeenCalledTimes(2);expect(privateResearch.cloudAppendMessage.mock.calls.every(call=>call[0].user.id===owner.id)).toBe(true);
 });
 it('denies guest bookmarks and account reassignment while retaining idempotent owned saved simulations',async()=>{
  expect((await handlePublicNfl(request('save',{gameId,analysisId}),['save'])).status).toBe(401);expect(privateStore.saveRecord).not.toHaveBeenCalled();expect(store.sharedJob).not.toHaveBeenCalled();
  state.user=owner;expect((await handlePublicNfl(request('save',{gameId,analysisId,user_id:'OTHER-OWNER'}),['save'])).status).toBe(400);
  const saved=await handlePublicNfl(request('save',{gameId,analysisId}),['save']);expect(saved.status).toBe(201);const first=await saved.json();expect(first.private).toBe(true);expect(privateStore.saveRecord.mock.calls[0][0].user).toEqual(owner);
  const repeated=await handlePublicNfl(request('save',{gameId,analysisId}),['save']);expect(repeated.status).toBe(200);expect((await repeated.json()).id).toBe(first.id);expect(privateStore.saveRecord).toHaveBeenCalledOnce();
 });
 it('rejects oversized public questions before any model/provider request',async()=>{
  const response=await handlePublicNfl(request('assistant',{gameId,message:'x'.repeat(2001)}),['assistant']);expect(response.status).toBe(400);expect(service.publicAssistant).not.toHaveBeenCalled();
 });
});
