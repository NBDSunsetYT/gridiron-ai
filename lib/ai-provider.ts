/** Server-only assistant transport. Import from API routes/services, never client components.
 * The OpenAI SDK also rejects browser execution by default. Credentials remain here;
 * probeAiProvider returns only an explicit, non-secret status projection. */
import OpenAI from 'openai';
import {ApiError} from './auth';

export type AiProviderName='openai'|'vercel-gateway';
type ReadinessReason='configured_unverified'|'missing_credentials'|'invalid_provider'|'invalid_model'|'credits_unverified'|'invalid_credit_response'|'authentication_failed'|'verification_required'|'insufficient_credits'|'rate_limited'|'provider_unavailable'|'included_credit_authorization_required'|'included_credits_authorized';
export type AiProviderStatus={
 provider:AiProviderName|'unsupported';
 model:string|null;
 configured:boolean;
 ready:boolean;
 reason:ReadinessReason;
 message:string;
 /** A credit probe never establishes that model generation/tool calls work. */
 generationVerified:false;
 credits?:{
  checkedAt:string;
  httpStatus:number|null;
  balanceUsd:number|null;
  totalUsedUsd:number|null;
  /** The documented credits endpoint does not identify free versus paid credits. */
  includedCreditEligibility:'unverified';
  includedCreditsAuthorized:boolean;
 };
};

const GATEWAY_URL='https://ai-gateway.vercel.sh/v1';
const GATEWAY_MODEL='openai/gpt-4.1-mini'; // Verified against /v1/models on 2026-10-30.
const gatewayCredential=()=>process.env.AI_GATEWAY_API_KEY?.trim()||process.env.VERCEL_OIDC_TOKEN?.trim();
function creditAmount(value:unknown):number|null{
 if(typeof value!=='number'&&(typeof value!=='string'||!/^\d+(?:\.\d+)?$/.test(value)))return null;
 const amount=Number(value);return Number.isFinite(amount)&&amount>=0?amount:null;
}

/** Read-only capability probe. No completions, key creation, top-ups or billing changes.
 * Call only behind authenticated, rate-limited, private/no-store server endpoints. */
export async function probeAiProvider(provider:AiProviderName|string=process.env.AI_PROVIDER||'openai'):Promise<AiProviderStatus>{
 if(provider!=='openai'&&provider!=='vercel-gateway')return{provider:'unsupported',model:null,configured:false,ready:false,reason:'invalid_provider',message:'AI_PROVIDER must be openai or vercel-gateway. No fallback provider was selected.',generationVerified:false};
 if(provider==='openai'){
  const configured=Boolean(process.env.OPENAI_API_KEY);
  return{provider,model:process.env.OPENAI_MODEL??'gpt-4.1-mini',configured,ready:configured,reason:configured?'configured_unverified':'missing_credentials',message:configured?'Server-side OpenAI credentials are configured; a live response has not been verified by this status check.':'GRIDIRON INTELLIGENCE requires a server-side OPENAI_API_KEY. Your records remain available; no mock responses are substituted.',generationVerified:false};
 }
 const model=process.env.AI_GATEWAY_MODEL||GATEWAY_MODEL,credential=gatewayCredential();
 const status:AiProviderStatus={provider,model,configured:Boolean(credential),ready:false,reason:'credits_unverified',message:'AI Gateway credit eligibility could not be verified. No generation request was made.',generationVerified:false,credits:{checkedAt:new Date().toISOString(),httpStatus:null,balanceUsd:null,totalUsedUsd:null,includedCreditEligibility:'unverified',includedCreditsAuthorized:process.env.AI_GATEWAY_INCLUDED_CREDITS_ALLOWED==='1'}};
 if(!/^[a-z0-9-]+\/[a-zA-Z0-9._/-]+$/.test(model)||model.length>200)return{...status,model:null,reason:'invalid_model',message:'AI_GATEWAY_MODEL must be an exact provider/model ID from the current AI Gateway model catalog.'};
 if(!credential)return{...status,reason:'missing_credentials',message:'Vercel AI Gateway requires server-side VERCEL_OIDC_TOKEN or AI_GATEWAY_API_KEY. No direct OpenAI fallback was attempted.'};
 try{
  const response=await fetch(`${GATEWAY_URL}/credits`,{method:'GET',headers:{Authorization:`Bearer ${credential}`,'Content-Type':'application/json'},cache:'no-store',redirect:'error',signal:AbortSignal.timeout(8000)});
  status.credits!.httpStatus=response.status;
  if(!response.ok){
   // Never return raw provider errors: they may contain identifiers or credentials.
   let verificationRequired=false;
   try{const error=await response.json();verificationRequired=error?.error?.type==='customer_verification_required'||error?.error?.code==='customer_verification_required';}catch{}
   if(response.status===401){status.reason='authentication_failed';status.message='AI Gateway rejected the server credential. Refresh the Vercel OIDC token or review the server configuration.';}
   else if(response.status===403&&verificationRequired){status.reason='verification_required';status.message='AI Gateway requires account verification before included credits are available. No payment method or billing settings were changed.';}
   else if(response.status===402){status.reason='insufficient_credits';status.message='AI Gateway credits or a provider budget are unavailable. No credits were purchased and no generation request was made.';}
   else if(response.status===429){status.reason='rate_limited';status.message='AI Gateway credit checks are rate limited. Retry later.';}
   else{status.reason='provider_unavailable';status.message='AI Gateway credit verification is unavailable. No generation request was made.';}
   return status;
  }
  const data=await response.json(),balance=creditAmount(data?.balance),totalUsed=creditAmount(data?.total_used);
  if(balance===null||totalUsed===null)return{...status,reason:'invalid_credit_response',message:'AI Gateway returned an unsupported credit response. Generation remains unavailable.'};
  status.credits!.balanceUsd=balance;status.credits!.totalUsedUsd=totalUsed;
  if(balance<=0)return{...status,reason:'insufficient_credits',message:'AI Gateway has no positive credit balance. No credits were purchased and no generation request was made.'};
  if(!status.credits!.includedCreditsAuthorized)return{...status,reason:'included_credit_authorization_required',message:'A positive AI Gateway balance does not identify included versus paid credits. Generation is disabled until an operator verifies included-credit-only use, disables paid auto top-ups, and explicitly sets AI_GATEWAY_INCLUDED_CREDITS_ALLOWED=1.'};
  return{...status,ready:true,reason:'included_credits_authorized',message:'The current credit balance is positive and the operator explicitly authorized verified included-credit-only use. Credit type and billing controls are operator-attested; live model generation has not been verified.'};
 }catch{
  return status;
 }
}

/** Construct only after readiness succeeds, before creating a conversation or sending
 * private records. Gateway is opt-in and cannot silently consume direct-provider funds. */
export async function createAiProviderClient(options:{timeout:number}){
 const status=await probeAiProvider();
 if(!status.ready)throw new ApiError(status.message,503);
 const gateway=status.provider==='vercel-gateway';
 const client=new OpenAI({apiKey:gateway?gatewayCredential():process.env.OPENAI_API_KEY,...(gateway?{baseURL:GATEWAY_URL}:{}),timeout:options.timeout,maxRetries:gateway?0:1});
 return{client,model:status.model!};
}
