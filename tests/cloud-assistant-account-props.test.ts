import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest';
const state=vi.hoisted(()=>({ledger:{} as any,threads:new Map<string,any>(),rpc:vi.fn(),settings:vi.fn(),provider:vi.fn(),completion:vi.fn(),dashboard:vi.fn(),nflDashboard:vi.fn(),detail:vi.fn(),performance:vi.fn(),gamePerformance:vi.fn(),scan:vi.fn(),sequence:0}));
vi.mock('../lib/cloud/context',async original=>{const real:any=await original();return{...real,rpc:(...args:any[])=>state.rpc(...args)};});
vi.mock('../lib/cloud/handler',()=>({cloudSettings:(...args:any[])=>state.settings(...args)}));
vi.mock('../lib/ai-provider',()=>({createAiProviderClient:(...args:any[])=>state.provider(...args)}));
vi.mock('../lib/player-props/service',()=>({propDashboard:(...args:any[])=>state.dashboard(...args),nflMarketDashboard:(...args:any[])=>state.nflDashboard(...args),propResearchDetail:(...args:any[])=>state.detail(...args),startPropScan:(...args:any[])=>state.scan(...args)}));
vi.mock('../lib/player-props/model-lab',()=>({getPropPerformance:(...args:any[])=>state.performance(...args)}));
vi.mock('../lib/player-props/game-performance',()=>({getGameMarketPerformance:(...args:any[])=>state.gamePerformance(...args)}));
vi.mock('../lib/cloud/research',async original=>{const real:any=await original();return{...real,
 cloudCreateConversation:vi.fn(async(ctx:any,title:string)=>{const id=`60000000-0000-4000-8000-${String(++state.sequence).padStart(12,'0')}`,value={id,title,owner:ctx.user.id,messages:[]};state.threads.set(id,value);return value;}),
 cloudConversation:vi.fn(async(ctx:any,id:string)=>{const row=state.threads.get(id);if(!row||row.owner!==ctx.user.id)throw Object.assign(new Error('Owned conversation not found.'),{status:404});return structuredClone(row);}),
 cloudAppendMessage:vi.fn(async(ctx:any,id:string,message:any)=>{const row=state.threads.get(id);if(!row||row.owner!==ctx.user.id)throw Object.assign(new Error('Owned conversation not found.'),{status:404});row.messages.push(structuredClone(message));return message;})};});
import {cloudAssistant} from '../lib/cloud/assistant';
import {ApiError} from '../lib/auth';
const ctx:any={request:new Request('https://gridiron.example/api/assistant'),user:{id:'SYNTHETIC-OWNER'},cookies:[],accessToken:'SYNTHETIC-TOKEN'};
const question=(text:string,conversationId?:string)=>({messages:[{role:'user',content:text}],...(conversationId?{conversationId}:{})});
const events=(text:string)=>text.split('\n\n').filter(line=>line.startsWith('data: ')&&line!=='data: [DONE]').map(line=>JSON.parse(line.slice(6)));
beforeEach(()=>{
 vi.clearAllMocks();vi.stubEnv('OPENAI_API_KEY','');vi.useFakeTimers({toFake:['Date']});vi.setSystemTime(new Date('2026-10-30T12:00:00Z'));state.sequence=0;state.threads.clear();
 state.ledger={transactions:[{type:'starting_balance',amountCents:50000,sportsbook:'DraftKings',date:'2026-10-01T12:00:00Z'},{type:'deposit',amountCents:10000,sportsbook:'DraftKings',date:'2026-10-05T12:00:00Z'},{type:'withdrawal',amountCents:15000,sportsbook:'DraftKings',date:'2026-10-10T12:00:00Z'}],bets:[{result:'won',stakeCents:4200,payoutCents:10000,sportsbook:'DraftKings',placedAt:'2026-10-20T12:00:00Z',settledAt:'2026-10-21T12:00:00Z'}],summary:{cashBalanceCents:50800,availableBalanceCents:50800,pendingExposureCents:0},accounts:[]};
 state.rpc.mockImplementation(async(c:any,name:string)=>{expect(c.user.id).toBe(ctx.user.id);expect(name).toBe('gridiron_ledger');return structuredClone(state.ledger);});state.settings.mockResolvedValue({timezone:'America/New_York'});state.provider.mockRejectedValue(new ApiError('OPENAI_API_KEY is required.',503));
 state.dashboard.mockResolvedValue({results:[{probability:{raw:.625,calibrated:null}}],sources:[],status:'partial'});state.detail.mockResolvedValue({id:'a'.repeat(64),probability:{raw:.625,calibrated:null},stale:false});state.performance.mockResolvedValue({status:'insufficient_evidence',n:0,brier:null});state.scan.mockResolvedValue({id:'SYNTHETIC-RUN',status:'queued',updated_at:new Date().toISOString()});
 state.nflDashboard.mockResolvedValue({provider:'DraftKings Predictions',providers:[{provider:'DraftKings Predictions',status:'unavailable',message:'No authorized feed is configured.'}],results:[],status:'unavailable'});
 state.gamePerformance.mockResolvedValue({status:'pending',sampleSize:null,overall:null,updatedAt:null,scope:'Prospective selected-side full-payout game contracts',message:'A scheduled final-score audit is pending.'});
});
afterEach(()=>{vi.unstubAllEnvs();vi.useRealTimers();});
describe('Private cloud assistant uses exact account reports and real player-prop tools',()=>{
 it('answers an explicit private withdrawal query without a provider and persists transparent SSE metadata and citations',async()=>{
  const response=await cloudAssistant(ctx,question('How much have I withdrawn this month?'));expect(response.status).toBe(200);expect(response.headers.get('cache-control')).toContain('no-store');expect(response.headers.get('x-gridiron-answer-method')).toBe('calculated_account_report');
  const data=events(await response.text());expect(data[0]).toMatchObject({generatedByAI:false,method:'calculated_account_report'});expect(data.find(value=>value.text)?.text).toContain('$150.00');expect(data.at(-1).citations[0]).toMatchObject({id:'read_ledger',timezone:'America/New_York',period:{from:'2026-10-01',toExclusive:'2026-11-01'}});expect(state.provider).not.toHaveBeenCalled();
  const saved=state.threads.get(response.headers.get('x-conversation-id')!);expect(saved.messages.map((message:any)=>message.role)).toEqual(['user','assistant']);expect(saved.messages[1].data).toMatchObject({generatedByAI:false,method:'calculated_account_report',values:{totalWithdrawalsCents:15000}});expect(state.ledger.summary.realizedPlCents).toBeUndefined();
 });
 it('calculates actual recorded P/L and current balances without treating capital movements as profit',async()=>{
  const response=await cloudAssistant(ctx,question('What is my realized P/L this month?'));const text=events(await response.text()).find(value=>value.text).text;expect(text).toContain('$58.00');expect(text).toContain('Deposits, withdrawals and transfers are excluded');expect(state.provider).not.toHaveBeenCalled();
  const balance=await cloudAssistant(ctx,question('What is my available balance?'));expect(events(await balance.text()).find(value=>value.text).text).toContain('$508.00');
 });
 it('refuses another owner conversation before reading private records or calling an external model',async()=>{
  const id='60000000-0000-4000-8000-000000000099';state.threads.set(id,{id,owner:'OTHER-OWNER',messages:[]});await expect(cloudAssistant(ctx,question('How much have I withdrawn this month?',id))).rejects.toMatchObject({status:404});expect(state.rpc).not.toHaveBeenCalled();expect(state.settings).not.toHaveBeenCalled();expect(state.provider).not.toHaveBeenCalled();
 });
 it('does not duplicate a previously stored pending user message or fabricate a generic missing-provider answer',async()=>{
  const id='60000000-0000-4000-8000-000000000099',content='How much have I withdrawn this month?';state.threads.set(id,{id,owner:ctx.user.id,messages:[{role:'user',content}]});await cloudAssistant(ctx,question(content,id));expect(state.threads.get(id).messages.map((message:any)=>message.role)).toEqual(['user','assistant']);
  const before=state.threads.size;await expect(cloudAssistant(ctx,question('Why did my player prop lose?'))).rejects.toMatchObject({status:503});expect(state.threads.size).toBe(before);
 });
 it('preserves failure and authentication boundaries instead of claiming a saved financial answer',async()=>{
  await expect(cloudAssistant({...ctx,user:null},question('What is my balance?'))).rejects.toMatchObject({status:401});expect(state.rpc).not.toHaveBeenCalled();state.rpc.mockRejectedValue(new ApiError('Account database unavailable',503));await expect(cloudAssistant(ctx,question('What is my balance?'))).rejects.toMatchObject({status:503});expect(state.threads.size).toBe(0);
 });
 function providerWithCalls(calls:any[]){let planned=false;vi.stubEnv('OPENAI_API_KEY','SYNTHETIC-TRANSPORT-ONLY');state.provider.mockResolvedValue({model:'SYNTHETIC-MODEL',client:{chat:{completions:{create:state.completion}}}});state.completion.mockImplementation(async(input:any)=>{if(input.stream)return(async function*(){yield{choices:[{delta:{content:'SYNTHETIC provider transport explanation.'}}]};})();if(!planned){planned=true;return{choices:[{message:{role:'assistant',content:null,tool_calls:calls.map((call,index)=>({id:'SYNTHETIC-'+index,type:'function',function:{name:call.name,arguments:JSON.stringify(call.args??{})}}))}}]};}return{choices:[{message:{role:'assistant',content:'SYNTHETIC plan complete'}}]};});}
 it('queries stored player research, exact snapshot and actual model performance without inventing calibration',async()=>{
  providerWithCalls([{name:'read_player_prop_research',args:{category:'receivingYards',gameId:'2026_08_BAL_BUF',playerName:'SYNTHETIC',limit:20}},{name:'read_prop_model_performance'},{name:'explain_player_prop',args:{id:'a'.repeat(64)}}]);
  const response=await cloudAssistant(ctx,question('Explain these receiving-yard model estimates.'));await response.text();expect(state.dashboard).toHaveBeenCalledWith({category:'receivingYards',gameId:'2026_08_BAL_BUF',search:'SYNTHETIC',provider:'DraftKings Predictions',limit:20});expect(state.performance).toHaveBeenCalledOnce();expect(state.detail).toHaveBeenCalledWith('a'.repeat(64));const message=state.completion.mock.calls.at(-1)![0] as any;const tool=message.messages.find((value:any)=>value.role==='tool');expect(JSON.parse(tool.content).results[0].probability.calibrated).toBeNull();expect(state.rpc).not.toHaveBeenCalled();
 });
 it('withholds an unrequested expensive scan even if the language model requests the tool',async()=>{
  providerWithCalls([{name:'analyze_player_props'}]);const response=await cloudAssistant(ctx,question('Explain the existing player-prop estimates.'));await response.text();expect(state.scan).not.toHaveBeenCalled();const message=state.completion.mock.calls.at(-1)![0] as any;expect(JSON.parse(message.messages.find((value:any)=>value.role==='tool').content).status).toBe('not_requested');
 });
 it('queues an actual scan only for an explicit analysis instruction and caps retrieval context',async()=>{
  providerWithCalls([{name:'analyze_player_props'}]);const response=await cloudAssistant(ctx,question('Analyze all available receiving-yard contracts.'));await response.text();expect(state.scan).toHaveBeenCalledWith('assistant');
  state.completion.mockReset();providerWithCalls([{name:'read_player_prop_research',args:{limit:21}}]);await expect(cloudAssistant(ctx,question('Explain the existing player-prop estimates.'))).rejects.toThrow();expect(state.dashboard).not.toHaveBeenCalled();
 });
 it('uses the primary DraftKings Predictions provider for all-NFL research without substituting another exchange',async()=>{
  providerWithCalls([{name:'read_nfl_market_research',args:{category:'totalPoints',gameId:'2026_08_BAL_BUF',ranking:'uncertainty',limit:20}},{name:'explain_nfl_contract',args:{id:'a'.repeat(64)}}]);
  const response=await cloudAssistant(ctx,question('Compare the Ravens versus Bills total on DraftKings Predictions.'));await response.text();
  expect(state.nflDashboard).toHaveBeenCalledWith({provider:'DraftKings Predictions',category:'totalPoints',gameId:'2026_08_BAL_BUF',ranking:'uncertainty',scope:'all',limit:20});expect(state.detail).toHaveBeenCalledWith('a'.repeat(64));
  const message=state.completion.mock.calls.at(-1)![0] as any,proof=JSON.parse(message.messages.find((value:any)=>value.role==='tool').content);
  expect(proof.providers[0].status).toBe('unavailable');expect(proof.results).toEqual([]);expect(state.scan).not.toHaveBeenCalled();
 });
 it('rejects an unrequested alternative-provider tool selection instead of inventing DraftKings prices',async()=>{
  providerWithCalls([{name:'read_nfl_market_research',args:{provider:'Kalshi'}}]);const response=await cloudAssistant(ctx,question('Show DraftKings Predictions NFL markets.'));await response.text();expect(state.nflDashboard).not.toHaveBeenCalled();
  const message=state.completion.mock.calls.at(-1)![0] as any;expect(JSON.parse(message.messages.find((value:any)=>value.role==='tool').content).status).toBe('provider_not_requested');
  state.completion.mockReset();providerWithCalls([{name:'read_nfl_market_research',args:{provider:'Kalshi'}}]);const negated=await cloudAssistant(ctx,question('Show only DraftKings Predictions; do not use Kalshi.'));await negated.text();expect(state.nflDashboard).not.toHaveBeenCalled();
 });
 it('permits an explicitly named alternative and validates categories and bounded context',async()=>{
  providerWithCalls([{name:'read_nfl_market_research',args:{provider:'Kalshi',category:'gameWinner'}}]);const response=await cloudAssistant(ctx,question('Show the separately labeled Kalshi game-winner research.'));await response.text();expect(state.nflDashboard).toHaveBeenCalledWith({provider:'Kalshi',category:'gameWinner',scope:'all',limit:10});
  state.completion.mockReset();state.nflDashboard.mockClear();providerWithCalls([{name:'read_nfl_market_research',args:{limit:21}}]);await expect(cloudAssistant(ctx,question('Show NFL markets.'))).rejects.toThrow();expect(state.nflDashboard).not.toHaveBeenCalled();
 });
 it('queues all-NFL research only for an explicit analysis instruction and never records a wager',async()=>{
  providerWithCalls([{name:'analyze_all_nfl_markets'}]);const response=await cloudAssistant(ctx,question('Analyze all NFL markets.'));await response.text();expect(state.scan).toHaveBeenCalledWith('all_nfl_assistant');expect(state.rpc).not.toHaveBeenCalled();
  state.completion.mockReset();state.scan.mockClear();providerWithCalls([{name:'analyze_all_nfl_markets'}]);const explain=await cloudAssistant(ctx,question('Why did the existing NFL market estimate change?'));await explain.text();expect(state.scan).not.toHaveBeenCalled();
 });
 it('requires real application evidence before streaming a provider statistical explanation',async()=>{
  providerWithCalls([]);await expect(cloudAssistant(ctx,question('Show the receiving-yard model probability.'))).rejects.toMatchObject({status:502});
  expect(state.completion.mock.calls[0][0].tool_choice).toBe('required');expect(state.completion.mock.calls.some(([request])=>request.stream)).toBe(false);
  expect([...state.threads.values()].flatMap(row=>row.messages).some(message=>message.role==='assistant')).toBe(false);
 });
 it('keeps game-market reliability separate from player accuracy and never invents metrics for an unevaluated category',async()=>{
  providerWithCalls([{name:'read_nfl_model_performance',args:{category:'gameWinner'}}]);const response=await cloudAssistant(ctx,question('How accurate is the game-winner model?'));await response.text();expect(state.gamePerformance).toHaveBeenCalledOnce();expect(state.performance).not.toHaveBeenCalled();
  const message=state.completion.mock.calls.at(-1)![0] as any,report=JSON.parse(message.messages.find((value:any)=>value.role==='tool').content);expect(report).toMatchObject({requestedCategory:'gameWinner',status:'pending',updatedAt:null,metrics:null});expect(report).not.toHaveProperty('brier');
 });
});
