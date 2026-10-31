import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest';
import {ApiError} from '../lib/auth';
import {playerPropFixture} from './fixtures/player-props';
const state=vi.hoisted(()=>({user:null as any,records:new Map<string,any>(),rows:null as any,scan:null as any}));
const service=vi.hoisted(()=>({startPropScan:vi.fn(),propDashboard:vi.fn(),propResearchDetail:vi.fn()}));
const nfl=vi.hoisted(()=>({publicGameDetail:vi.fn(),loadSchedule:vi.fn()}));
const auth=vi.hoisted(()=>({cloudContext:vi.fn()}));
const privateStore=vi.hoisted(()=>({record:vi.fn(),records:vi.fn(),saveRecord:vi.fn()}));
const privateMessages=vi.hoisted(()=>({cloudCreateConversation:vi.fn(),cloudAppendMessage:vi.fn(),cloudContracts:vi.fn()}));
const shared=vi.hoisted(()=>({propWrite:vi.fn(),propBatch:vi.fn(),publicRateLimit:vi.fn()}));
const privateJobs=vi.hoisted(()=>({readPrivatePropResearch:vi.fn(),queuePrivatePropResearch:vi.fn()}));
vi.mock('next/server',()=>({after:vi.fn()}));
vi.mock('../lib/player-props/service',()=>service);
vi.mock('../lib/public-nfl/service',()=>nfl);
vi.mock('../lib/public-nfl/store',()=>({publicRateLimit:shared.publicRateLimit}));
vi.mock('../lib/player-props/store',()=>({propWrite:shared.propWrite,propBatch:shared.propBatch}));
vi.mock('../lib/cloud/context',async original=>({...await original<typeof import('../lib/cloud/context')>(),cloudContext:auth.cloudContext}));
vi.mock('../lib/cloud/store',()=>privateStore);
vi.mock('../lib/cloud/research',()=>privateMessages);
vi.mock('../lib/player-props/private-research',()=>privateJobs);
vi.mock('../lib/player-props/model-lab',()=>({getPropPerformance:async()=>({status:'insufficient_evidence',eligibleResolved:0,overall:null})}));
vi.mock('../lib/player-props/providers',()=>({normalizeVerifiedManualProp:vi.fn((raw:any)=>raw)}));
vi.mock('../lib/ai-provider',()=>({createAiProviderClient:vi.fn(async()=>({model:'SYNTHETIC-TEST-TRANSPORT',client:{chat:{completions:{create:async()=>({choices:[{message:{content:'SYNTHETIC answer may echo private question content.'}}]})}}}}))}));
import {handlePlayerProps} from '../lib/player-props/handler';

const owner={id:'10000000-0000-4000-8000-000000000006',email:'SYNTHETIC-PROP-QA@example.test'},researchId='a'.repeat(64);
function request(path:string,body?:unknown,origin='https://gridiron.example.test',contentType='application/json'){
 return new Request('https://gridiron.example.test/api/props/'+path,{method:body===undefined?'GET':'POST',headers:{Origin:origin,'Content-Type':contentType},body:body===undefined?undefined:JSON.stringify(body)});
}
beforeEach(()=>{
 vi.clearAllMocks();vi.stubEnv('APP_URL','https://gridiron.example.test');vi.stubEnv('APP_ORIGIN','');vi.stubEnv('OPENAI_API_KEY','');
 state.user=null;state.records.clear();const f=playerPropFixture();state.scan=f.scan;state.rows={...f.receiverYes,id:researchId};
 service.startPropScan.mockResolvedValue({id:'SYNTHETIC-SCAN',status:'queued'});service.propDashboard.mockImplementation(async()=>structuredClone(state.scan));service.propResearchDetail.mockImplementation(async(id:string)=>{if(id!==researchId)throw new ApiError('Research snapshot not found.',404);return structuredClone(state.rows);});
 auth.cloudContext.mockImplementation(async(req:Request)=>({request:req,user:state.user,client:{},accessToken:state.user?'SYNTHETIC-SESSION':null,cookies:[]}));
 privateStore.record.mockImplementation(async(ctx:any,id:string)=>state.records.get(ctx.user.id+'|'+id)??null);
 privateStore.records.mockResolvedValue([]);privateStore.saveRecord.mockImplementation(async(ctx:any,_kind:string,value:any,options:any)=>{const row={...value,id:options?.id??'SYNTHETIC-PRIVATE-RECORD'};state.records.set(ctx.user.id+'|'+row.id,row);return row;});
 privateMessages.cloudCreateConversation.mockResolvedValue({id:'SYNTHETIC-PRIVATE-CONVERSATION'});privateMessages.cloudAppendMessage.mockResolvedValue({});
 privateJobs.queuePrivatePropResearch.mockResolvedValue({id:'SYNTHETIC-PRIVATE-JOB',status:'queued',actualWagerRecorded:false});
 nfl.loadSchedule.mockResolvedValue({games:[]});nfl.publicGameDetail.mockResolvedValue(f.nfl.detail);
});
afterEach(()=>vi.unstubAllEnvs());

describe('Public prop research and private account boundaries',()=>{
 it('opens public research and calibration status without creating an identity or private writes',async()=>{
  expect((await handlePlayerProps(request(''))).status).toBe(200);expect(auth.cloudContext).not.toHaveBeenCalled();
  const performance=await handlePlayerProps(request('performance'),['performance']);expect(performance.status).toBe(200);expect((await performance.json()).overall).toBeNull();expect(privateStore.saveRecord).not.toHaveBeenCalled();expect(privateMessages.cloudCreateConversation).not.toHaveBeenCalled();
 });
 it('allows only an empty one-tap scan request, never client statistics, arbitrary URLs or account overrides',async()=>{
  const response=await handlePlayerProps(request('analyze',{}),['analyze']);expect(response.status).toBe(202);expect(service.startPropScan).toHaveBeenCalledOnce();expect(response.headers.get('Cache-Control')).toBe('no-store');
  service.startPropScan.mockClear();for(const input of[{user_id:owner.id},{csv:'SYNTHETIC-CLIENT-STATS'},{sourceUrl:'http://169.254.169.254/metadata'},{model:{rows:[]}},{simulations:100000}])expect((await handlePlayerProps(request('analyze',input),['analyze'])).status).toBe(400);
  expect(service.startPropScan).not.toHaveBeenCalled();
 });
 it('rejects cross-origin, non-JSON and rate-limited scans before research work',async()=>{
  expect((await handlePlayerProps(request('analyze',{},'https://attacker.example.test'),['analyze'])).status).toBe(403);
  expect((await handlePlayerProps(request('analyze',{},undefined,'text/plain'),['analyze'])).status).toBe(415);
  shared.publicRateLimit.mockRejectedValueOnce(new ApiError('Rate limit reached.',429));expect((await handlePlayerProps(request('analyze',{}),['analyze'])).status).toBe(429);expect(service.startPropScan).not.toHaveBeenCalled();
 });
 it('requires app identity for bookmarks, manual contracts, combinations and what-if records',async()=>{
  for(const[path,body]of[['save',{researchId}],['manual',{contract:{gameId:'2026_08_BAL_BUF'}}],['combinations',{researchIds:[researchId,'b'.repeat(64)]}],['what-if',{gameId:'2026_08_BAL_BUF',playerId:'00-0000001',status:'inactive'}]] as const){expect((await handlePlayerProps(request(path,body),[path])).status).toBe(401);}
  expect((await handlePlayerProps(request('manual'),['manual'])).status).toBe(401);expect(privateStore.saveRecord).not.toHaveBeenCalled();expect(privateJobs.queuePrivatePropResearch).not.toHaveBeenCalled();
 });
 it('binds idempotent private saves to verified owner context and rejects user reassignment',async()=>{
  state.user=owner;expect((await handlePlayerProps(request('save',{researchId,user_id:'OTHER-OWNER'}),['save'])).status).toBe(400);
  const first=await handlePlayerProps(request('save',{researchId}),['save']),firstData=await first.json();expect(first.status).toBe(201);expect(firstData.private).toBe(true);expect(first.headers.get('Cache-Control')).toMatch(/private.*no-store/);
  const repeated=await handlePlayerProps(request('save',{researchId}),['save']);expect(repeated.status).toBe(200);expect((await repeated.json()).id).toBe(firstData.id);expect(privateStore.saveRecord).toHaveBeenCalledOnce();expect(privateStore.saveRecord.mock.calls[0][0].user.id).toBe(owner.id);
  state.user={...owner,id:'20000000-0000-4000-8000-000000000006'};const other=await handlePlayerProps(request('save',{researchId}),['save']);expect((await other.json()).id).not.toBe(firstData.id);
 });
 it('keeps guest questions and AI answers out of every shared write or cache',async()=>{
  vi.stubEnv('OPENAI_API_KEY','SYNTHETIC-TRANSPORT-KEY-NOT-REAL');const question='SYNTHETIC PRIVATE ADDRESS AND PREFERENCE - explain this receiving market';
  const response=await handlePlayerProps(request('assistant',{message:question}),['assistant']);expect(response.status).toBe(200);expect((await response.json()).historySaved).toBe(false);
  expect(privateMessages.cloudCreateConversation).not.toHaveBeenCalled();expect(privateStore.saveRecord).not.toHaveBeenCalled();expect(shared.propWrite).not.toHaveBeenCalled();expect(shared.propBatch).not.toHaveBeenCalled();expect(JSON.stringify(service.propDashboard.mock.calls)).not.toContain(question);
 });
 it('saves signed-in conversation history only under the verified owner, with no public question cache',async()=>{
  state.user=owner;const question='SYNTHETIC PRIVATE withdrawal context, explain this stored contract';
  const response=await handlePlayerProps(request('assistant',{researchId,message:question}),['assistant']);expect(response.status).toBe(200);expect((await response.json()).historySaved).toBe(true);expect(response.headers.get('Cache-Control')).toMatch(/private.*no-store/);
  expect(privateMessages.cloudAppendMessage).toHaveBeenCalledTimes(2);expect(privateMessages.cloudAppendMessage.mock.calls.every(([ctx])=>ctx.user.id===owner.id)).toBe(true);expect(privateMessages.cloudAppendMessage.mock.calls[0][2].content).toBe(question);expect(shared.propWrite).not.toHaveBeenCalled();expect(shared.propBatch).not.toHaveBeenCalled();
 });
 it('rejects unsupported filters and oversized questions, preserves source404 and never starts hidden compute',async()=>{
  expect((await handlePlayerProps(request('?category=UNSUPPORTED'))).status).toBe(400);
  expect((await handlePlayerProps(request('assistant',{message:'x'.repeat(2001)}),['assistant'])).status).toBe(400);
  expect((await handlePlayerProps(request('results/'+'b'.repeat(64)),['results','b'.repeat(64)])).status).toBe(404);
  expect(service.startPropScan).not.toHaveBeenCalled();expect(shared.propWrite).not.toHaveBeenCalled();
 });
});
