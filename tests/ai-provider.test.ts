/** Provider transport is explicitly stubbed. No model calls, credit use, or billing
 * changes are made by these capability/security tests. */
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
const transport=vi.hoisted(()=>({construct:vi.fn(),create:vi.fn()}));
vi.mock('openai',()=>({default:class MockOpenAI{constructor(options:unknown){transport.construct(options);}chat={completions:{create:transport.create}};}}));
import {createAiProviderClient,probeAiProvider} from '../lib/ai-provider';
const gatewayToken='SYNTHETIC OIDC TOKEN NEVER A REAL CREDENTIAL';
const gatewayKey='SYNTHETIC GATEWAY KEY NEVER A REAL CREDENTIAL';
const directKey='SYNTHETIC OPENAI KEY NEVER A REAL CREDENTIAL';
let fetcher:ReturnType<typeof vi.fn>;
beforeEach(()=>{
 for(const name of ['AI_PROVIDER','OPENAI_API_KEY','OPENAI_MODEL','AI_GATEWAY_MODEL','AI_GATEWAY_API_KEY','VERCEL_OIDC_TOKEN','AI_GATEWAY_INCLUDED_CREDITS_ALLOWED'])vi.stubEnv(name,'');
 transport.construct.mockReset();transport.create.mockReset();fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);
});
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
function enableGateway(){vi.stubEnv('AI_PROVIDER','vercel-gateway');vi.stubEnv('VERCEL_OIDC_TOKEN',gatewayToken);}
function credits(balance='5.00',total_used='0.00'){fetcher.mockResolvedValue(Response.json({balance,total_used}));}
describe('Server-only AI provider readiness and spend guard',()=>{
 it('preserves direct OpenAI as the default without probing Gateway or claiming a verified response',async()=>{
  vi.stubEnv('OPENAI_API_KEY',directKey);vi.stubEnv('OPENAI_MODEL','gpt-4.1-mini');
  const status=await probeAiProvider();expect(status).toMatchObject({provider:'openai',configured:true,ready:true,generationVerified:false,reason:'configured_unverified'});
  const result=await createAiProviderClient({timeout:30000});expect(result.model).toBe('gpt-4.1-mini');expect(transport.construct).toHaveBeenCalledWith({apiKey:directKey,timeout:30000,maxRetries:1});expect(fetcher).not.toHaveBeenCalled();expect(transport.create).not.toHaveBeenCalled();
 });
 it('reports missing direct credentials with503 and never silently consumes Gateway credits',async()=>{
  vi.stubEnv('VERCEL_OIDC_TOKEN',gatewayToken);expect(await probeAiProvider()).toMatchObject({provider:'openai',configured:false,ready:false,reason:'missing_credentials'});
  await expect(createAiProviderClient({timeout:30000})).rejects.toMatchObject({status:503});expect(fetcher).not.toHaveBeenCalled();expect(transport.construct).not.toHaveBeenCalled();
 });
 it('rejects an unsupported provider without choosing a fallback',async()=>{
  vi.stubEnv('AI_PROVIDER','SYNTHETIC-UNSUPPORTED');vi.stubEnv('OPENAI_API_KEY',directKey);
  expect(await probeAiProvider()).toMatchObject({provider:'unsupported',ready:false,reason:'invalid_provider'});await expect(createAiProviderClient({timeout:30000})).rejects.toMatchObject({status:503});expect(fetcher).not.toHaveBeenCalled();
 });
 it('rejects missing Gateway credentials even when direct OpenAI is configured',async()=>{
  vi.stubEnv('AI_PROVIDER','vercel-gateway');vi.stubEnv('OPENAI_API_KEY',directKey);const status=await probeAiProvider();expect(status).toMatchObject({provider:'vercel-gateway',ready:false,reason:'missing_credentials'});expect(fetcher).not.toHaveBeenCalled();expect(transport.construct).not.toHaveBeenCalled();
 });
 it('permits an explicit read-only Gateway probe while direct OpenAI remains the selected provider',async()=>{
  vi.stubEnv('VERCEL_OIDC_TOKEN',gatewayToken);credits();const status=await probeAiProvider('vercel-gateway');expect(status.provider).toBe('vercel-gateway');expect(status.ready).toBe(false);expect(fetcher).toHaveBeenCalledTimes(1);expect(transport.create).not.toHaveBeenCalled();
 });
 it('uses a fresh server OIDC token only on the fixed credit endpoint and projects non-secret response fields',async()=>{
  enableGateway();fetcher.mockResolvedValue(Response.json({balance:'5.00',total_used:'0.25',unexpectedSecret:gatewayToken}));const status=await probeAiProvider();
  expect(fetcher).toHaveBeenCalledWith('https://ai-gateway.vercel.sh/v1/credits',expect.objectContaining({method:'GET',headers:{Authorization:`Bearer ${gatewayToken}`,'Content-Type':'application/json'},cache:'no-store',redirect:'error',signal:expect.any(AbortSignal)}));
  expect(status).toMatchObject({configured:true,ready:false,generationVerified:false,reason:'included_credit_authorization_required',credits:{balanceUsd:5,totalUsedUsd:0.25,includedCreditEligibility:'unverified',includedCreditsAuthorized:false,httpStatus:200}});expect(JSON.stringify(status)).not.toContain(gatewayToken);expect(JSON.stringify(status)).not.toContain('unexpectedSecret');
  vi.stubEnv('VERCEL_OIDC_TOKEN','SYNTHETIC ROTATED OIDC');await probeAiProvider();expect(fetcher.mock.calls[1][1].headers.Authorization).toBe('Bearer SYNTHETIC ROTATED OIDC');
 });
 it('requires included-credit authorization even for a positive balance',async()=>{
  enableGateway();credits();await expect(createAiProviderClient({timeout:30000})).rejects.toMatchObject({status:503});expect(transport.construct).not.toHaveBeenCalled();expect(transport.create).not.toHaveBeenCalled();
 });
 it('constructs the opt-in OpenAI-compatible Gateway transport only after explicit included-credit authorization',async()=>{
  enableGateway();vi.stubEnv('AI_GATEWAY_INCLUDED_CREDITS_ALLOWED','1');credits();const result=await createAiProviderClient({timeout:60000});expect(result.model).toBe('openai/gpt-4.1-mini');expect(transport.construct).toHaveBeenCalledWith({apiKey:gatewayToken,baseURL:'https://ai-gateway.vercel.sh/v1',timeout:60000,maxRetries:0});expect(transport.create).not.toHaveBeenCalled();
 });
 it('uses an existing server Gateway key when explicitly configured, without exposing either credential',async()=>{
  enableGateway();vi.stubEnv('AI_GATEWAY_API_KEY',gatewayKey);credits();const status=await probeAiProvider();expect(fetcher.mock.calls[0][1].headers.Authorization).toBe(`Bearer ${gatewayKey}`);expect(JSON.stringify(status)).not.toContain(gatewayKey);expect(JSON.stringify(status)).not.toContain(gatewayToken);
 });
 it.each(['0.00','0'])('withholds generation for exhausted credits%s even after operator authorization',async balance=>{
  enableGateway();vi.stubEnv('AI_GATEWAY_INCLUDED_CREDITS_ALLOWED','1');credits(balance);expect(await probeAiProvider()).toMatchObject({ready:false,reason:'insufficient_credits'});await expect(createAiProviderClient({timeout:30000})).rejects.toMatchObject({status:503});expect(transport.construct).not.toHaveBeenCalled();
 });
 it.each([{balance:'Infinity',total_used:'0'},{balance:'5',total_used:undefined},{balance:-1,total_used:0},{balance:true,total_used:'0'},{balance:'5',total_used:'NaN'}])('fails closed on an unsupported credit payload%j',async payload=>{
  enableGateway();vi.stubEnv('AI_GATEWAY_INCLUDED_CREDITS_ALLOWED','1');fetcher.mockResolvedValue(Response.json(payload));expect(await probeAiProvider()).toMatchObject({ready:false,reason:'invalid_credit_response',credits:{balanceUsd:null,totalUsedUsd:null}});expect(transport.construct).not.toHaveBeenCalled();
 });
 it.each([[401,'authentication_failed'],[402,'insufficient_credits'],[429,'rate_limited'],[503,'provider_unavailable']] as const)('handles provider HTTP%s without leaking upstream error text',async(httpStatus,reason)=>{
  enableGateway();fetcher.mockResolvedValue(Response.json({error:{message:gatewayToken}},{status:httpStatus}));const status=await probeAiProvider();expect(status).toMatchObject({ready:false,reason,credits:{httpStatus}});expect(JSON.stringify(status)).not.toContain(gatewayToken);expect(transport.create).not.toHaveBeenCalled();
 });
 it('identifies an account verification requirement without creating a payment method or exposing action links',async()=>{
  enableGateway();fetcher.mockResolvedValue(Response.json({error:{type:'customer_verification_required',action_url:`https://example.test/${gatewayToken}`}},{status:403}));const status=await probeAiProvider();expect(status.reason).toBe('verification_required');expect(JSON.stringify(status)).not.toContain('action_url');expect(JSON.stringify(status)).not.toContain(gatewayToken);expect(fetcher).toHaveBeenCalledTimes(1);
 });
 it('withholds generation after a failed network check without exposing transport exception details',async()=>{
  enableGateway();vi.stubEnv('AI_GATEWAY_INCLUDED_CREDITS_ALLOWED','1');fetcher.mockRejectedValue(new Error(gatewayToken));const status=await probeAiProvider();expect(status).toMatchObject({ready:false,reason:'credits_unverified',credits:{httpStatus:null}});expect(JSON.stringify(status)).not.toContain(gatewayToken);await expect(createAiProviderClient({timeout:30000})).rejects.toMatchObject({status:503});expect(transport.construct).not.toHaveBeenCalled();
 });
 it('rejects malformed Gateway model IDs before any credit request',async()=>{
  enableGateway();vi.stubEnv('AI_GATEWAY_MODEL','gpt-4.1-mini');expect(await probeAiProvider()).toMatchObject({ready:false,reason:'invalid_model',model:null});expect(fetcher).not.toHaveBeenCalled();
 });
});
