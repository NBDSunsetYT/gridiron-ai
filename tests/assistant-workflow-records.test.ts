/** Actual temporary ledger/conversation integration. OpenAI transport is explicitly
 * stubbed: these checks do not establish a live model response or paid API access. */
import {afterAll,afterEach,beforeAll,beforeEach,describe,expect,it,vi} from 'vitest';
import {randomUUID} from 'node:crypto';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const provider=vi.hoisted(()=>({create:vi.fn(),Error:class SyntheticProviderError extends Error{status=500;}}));
vi.mock('openai',()=>({default:class MockOpenAI{static APIError=provider.Error;chat={completions:{create:provider.create}};}}));
const directory=mkdtempSync(join(tmpdir(),'gridiron-assistant-records-'));
process.env.DATA_DIR=directory;
let db:typeof import('../lib/db'),auth:typeof import('../lib/auth'),ledger:typeof import('../lib/ledger'),research:typeof import('../lib/research-store'),route:typeof import('../app/api/assistant/route');
let owner:string,other:string,ownerToken:string,otherToken:string;
const question='What were my October withdrawals and realized P/L?';
beforeAll(async()=>{
 db=await import('../lib/db');auth=await import('../lib/auth');ledger=await import('../lib/ledger');research=await import('../lib/research-store');route=await import('../app/api/assistant/route');
 owner=randomUUID();other=randomUUID();
 for(const id of [owner,other])db.getDb().prepare('INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)').run(id,`${id}@example.test`,'SYNTHETIC TEST HASH',new Date().toISOString());
 ownerToken=auth.newSession(owner);otherToken=auth.newSession(other);
 ledger.postTransaction(owner,{type:'starting_balance',amount:'500.00',sportsbook:'DraftKings',date:'2026-10-01T12:00:00Z'});
 ledger.postTransaction(owner,{type:'deposit',amount:'100.00',sportsbook:'DraftKings',date:'2026-10-02T12:00:00Z'});
 ledger.postTransaction(owner,{type:'withdrawal',amount:'150.00',sportsbook:'DraftKings',date:'2026-10-03T12:00:00Z'});
 const bet=ledger.placeBet(owner,{sportsbook:'DraftKings',event:'SYNTHETIC TEST EVENT',market:'SYNTHETIC market',selection:'SYNTHETIC selection',stake:'100.00',odds:-110,placedAt:'2026-10-04T11:00:00Z'});
 ledger.settleBet(owner,{id:bet.id,result:'won',payout:'175.00',settledAt:'2026-10-04T12:00:00Z'});
 ledger.postTransaction(other,{type:'deposit',amount:'777.77',sportsbook:'Hard Rock',note:'OTHER OWNER PRIVATE SYNTHETIC RECORD'});
});
beforeEach(()=>{provider.create.mockReset();vi.stubEnv('AI_PROVIDER','');vi.stubEnv('OPENAI_API_KEY','SYNTHETIC PROVIDER STUB ONLY');vi.stubEnv('APP_ORIGIN','http://localhost:3000');});
afterEach(()=>vi.unstubAllEnvs());
afterAll(()=>{db.closeDb();rmSync(directory,{recursive:true,force:true});});
function request(token=ownerToken,conversationId?:string){return new Request('http://localhost:3000/api/assistant',{method:'POST',headers:{'content-type':'application/json',origin:'http://localhost:3000',cookie:`${auth.SESSION_COOKIE}=${token}`},body:JSON.stringify({conversationId,messages:[{role:'user',content:question}]})});}
describe('Assistant retrieves persisted owned records with provider transport stubbed',()=>{
 it('reports a missing provider key explicitly without inventing an answer or creating a conversation',async()=>{
  vi.stubEnv('OPENAI_API_KEY','');const before=research.listConversations(owner).length;const response=await route.POST(request());expect(response.status).toBe(503);expect((await response.json()).error).toContain('OPENAI_API_KEY');expect(research.listConversations(owner)).toHaveLength(before);expect(provider.create).not.toHaveBeenCalled();
 });
 it('withholds unconfigured Gateway requests without saving conversation text or falling back to direct OpenAI',async()=>{
  vi.stubEnv('AI_PROVIDER','vercel-gateway');vi.stubEnv('AI_GATEWAY_API_KEY','');vi.stubEnv('VERCEL_OIDC_TOKEN','');const before=research.listConversations(owner).length;const response=await route.POST(request());expect(response.status).toBe(503);expect((await response.json()).error).toContain('VERCEL_OIDC_TOKEN');expect(research.listConversations(owner)).toHaveLength(before);expect(provider.create).not.toHaveBeenCalled();
 });
 it('checks Gateway credits without sending private records and refuses unapproved credit use',async()=>{
  vi.stubEnv('AI_PROVIDER','vercel-gateway');vi.stubEnv('AI_GATEWAY_API_KEY','');vi.stubEnv('VERCEL_OIDC_TOKEN','SYNTHETIC GATEWAY TOKEN');vi.stubEnv('AI_GATEWAY_INCLUDED_CREDITS_ALLOWED','');const fetcher=vi.spyOn(globalThis,'fetch').mockResolvedValue(Response.json({balance:'5.00',total_used:'0.00'}));
  try{const before=research.listConversations(owner).length;const response=await route.POST(request());expect(response.status).toBe(503);expect((await response.json()).error).toContain('included versus paid');expect(research.listConversations(owner)).toHaveLength(before);expect(provider.create).not.toHaveBeenCalled();expect(fetcher).toHaveBeenCalledWith('https://ai-gateway.vercel.sh/v1/credits',expect.objectContaining({method:'GET'}));expect(fetcher.mock.calls[0][1]?.body).toBeUndefined();}finally{fetcher.mockRestore();}
 });
 it('calculates actual period totals, excludes the other owner, and persists streamed conversation citations',async()=>{
  provider.create.mockImplementation(async(input:any)=>{
   if(input.stream){const actual=JSON.parse(input.messages.find((m:any)=>m.role==='tool').content);return(async function*(){yield{choices:[{delta:{content:`Recorded withdrawals: ${actual.summary.totalWithdrawalsCents} cents; realized P/L: ${actual.summary.realizedPlCents} cents. [ledger]`}}]};})();}
   if(input.messages.some((m:any)=>m.role==='tool'))return{choices:[{message:{role:'assistant',content:'SYNTHETIC planning response'}}]};
   return{choices:[{message:{role:'assistant',content:null,tool_calls:[{id:'synthetic-read-ledger',type:'function',function:{name:'read_ledger',arguments:JSON.stringify({from:'2026-10-01T00:00:00Z',to:'2026-11-01T00:00:00Z'})}}]}}]};
  });
  const before=ledger.getLedger(owner).summary;const response=await route.POST(request());expect(response.status).toBe(200);expect(response.headers.get('content-type')).toBe('text/event-stream');expect(response.headers.get('cache-control')).toContain('no-store');const text=await response.text();expect(text).toContain('Recorded withdrawals: 15000 cents; realized P/L: 7500 cents');
  const tool=provider.create.mock.calls.flatMap(([input])=>input.messages).find((m:any)=>m.role==='tool');const actual=JSON.parse(tool.content);expect(actual.summary).toMatchObject({totalWithdrawalsCents:15000,totalDepositsCents:10000,realizedPlCents:7500,settledBets:1});expect(JSON.stringify(actual)).not.toContain('OTHER OWNER PRIVATE');expect(JSON.stringify(actual)).not.toContain('77777');
  const id=response.headers.get('x-conversation-id')!;const stored=research.getConversation(owner,id);expect(stored.messages.map(m=>m.role)).toEqual(['user','assistant']);expect(stored.messages[1].content).toContain('15000 cents');expect(stored.messages[1].data.citations).toContainEqual(expect.objectContaining({id:'ledger'}));expect(ledger.getLedger(owner).summary).toEqual(before);
 });
 it('rejects another account conversation before invoking the provider',async()=>{
  const conversation=research.createConversation(owner,'SYNTHETIC private research');const response=await route.POST(request(otherToken,conversation.id));expect(response.status).toBe(404);expect(provider.create).not.toHaveBeenCalled();expect(research.getConversation(owner,conversation.id).messages).toEqual([]);
 });
 it('reports provider failure and keeps only the actual user message rather than fabricating a response',async()=>{
  provider.create.mockRejectedValue(new provider.Error('SYNTHETIC provider offline'));const response=await route.POST(request());expect(response.status).toBe(502);expect((await response.json()).error).toContain('OpenAI could not complete');const conversations=research.listConversations(owner);const failed=conversations.map(c=>research.getConversation(owner,c.id)).find(c=>c.messages.length===1);expect(failed?.messages[0]).toMatchObject({role:'user',content:question});
 });
});
