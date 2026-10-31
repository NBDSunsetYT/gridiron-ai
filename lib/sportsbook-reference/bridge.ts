/** Only the internal bridge token exists in Vercel. The BALLDONTLIE API key is
 * read exclusively by the Render gateway after its platform/auth guards. */
import type {BdlResponse,ReferenceDiagnostic} from './types';
export const BDL_NFL_DOCS='https://nfl.balldontlie.io';
const resources=new Set(['status','verify','teams','players','games','stats','injuries','snap-counts','designations','odds','opening-odds','player-props','opening-player-props']);
export function bridgeDiagnostic(code:string,message:string,extra:Partial<ReferenceDiagnostic>={}):ReferenceDiagnostic{return{code,message,checkedAt:new Date().toISOString(),httpStatus:null,retryable:false,requiresOperator:false,...extra};}
function renderBase(){const raw=process.env.GRIDIRON_RENDER_DATA_URL;if(!raw)return null;const u=new URL(raw);if(u.protocol!=='https:'||u.username||u.password||u.port&&u.port!=='443'||!u.hostname.endsWith('.onrender.com')||u.search||u.hash)throw Error('Invalid Render data gateway configuration.');return u;}
export function sportsDataBridgeConfiguration():ReferenceDiagnostic|null{
 if(!process.env.GRIDIRON_RENDER_DATA_URL)return bridgeDiagnostic('render_backend_required','The Render data gateway is not connected. No BALLDONTLIE request has been made.',{requiresOperator:true});
 try{renderBase();}catch{return bridgeDiagnostic('bridge_configuration_invalid','The Render data gateway address must be a verified secure Render service.',{requiresOperator:true});}
 const token=process.env.GRIDIRON_DATA_BRIDGE_TOKEN;if(!token||token.length<32||/[\r\n]/.test(token))return bridgeDiagnostic('bridge_not_configured','The secure server-to-server data bridge is not configured.',{requiresOperator:true});return null;
}
function unavailable(problem:ReferenceDiagnostic):BdlResponse{return{provider:'BALLDONTLIE',sport:'NFL',dataFamily:'sportsbook_reference',status:'unavailable',checkedAt:problem.checkedAt,items:[],records:[],complete:false,nextCursor:null,diagnostic:problem,source:{documentationUrl:BDL_NFL_DOCS}};}
export async function readNflSportsData(resource:string,params:Record<string,string|number|Array<string|number>>={},transport:typeof fetch=fetch):Promise<BdlResponse>{
 const problem=sportsDataBridgeConfiguration();if(problem)return unavailable(problem);
 if(!resources.has(resource))return unavailable(bridgeDiagnostic('unsupported_resource','This NFL reference-data resource is unsupported.'));
 const base=renderBase()!,url=new URL('/data/nfl/'+resource,base),token=process.env.GRIDIRON_DATA_BRIDGE_TOKEN!;
 if(url.href.includes(token))return unavailable(bridgeDiagnostic('bridge_configuration_invalid','The data gateway address must not contain a credential.',{requiresOperator:true}));
 for(const[key,value]of Object.entries(params)){const values=Array.isArray(value)?value:[value];if(values.length>100)return unavailable(bridgeDiagnostic('invalid_request','The NFL query exceeds its bounded size.'));for(const v of values){const text=String(v);if(text.length>100||/[\r\n]/.test(text))return unavailable(bridgeDiagnostic('invalid_request','A bounded NFL query is required.'));url.searchParams.append(Array.isArray(value)&&!key.endsWith('[]')?key+'[]':key,text);}}
 try{
  const response=await transport(url,{method:'GET',headers:{Authorization:'Bearer '+token,Accept:'application/json'},cache:'no-store',redirect:'error',signal:AbortSignal.timeout(20000)});
  if(Number(response.headers.get('content-length')||0)>10_000_000)return unavailable(bridgeDiagnostic('unsupported_response','The data gateway response exceeds its safe bound.'));
  const reader=response.body?.getReader();if(!reader)return unavailable(bridgeDiagnostic('unsupported_response','The data gateway returned no readable response.'));
  const chunks:Uint8Array[]=[];let size=0;for(;;){const{done,value}=await reader.read();if(done)break;size+=value.length;if(size>10_000_000){await reader.cancel();return unavailable(bridgeDiagnostic('unsupported_response','The data gateway response exceeds its safe bound.'));}chunks.push(value);}
  const raw=Buffer.concat(chunks).toString('utf8');if(raw.includes(token))return unavailable(bridgeDiagnostic('unsafe_response','The gateway response could not be verified safely.'));
  let body:any;try{body=JSON.parse(raw);}catch{return unavailable(bridgeDiagnostic('unsupported_response','The data gateway did not return a verified JSON dataset.',{httpStatus:response.status}));}
  if(!response.ok){if(body?.sport&&body.sport!=='NFL'||body?.provider&&body.provider!=='BALLDONTLIE')return unavailable(bridgeDiagnostic('source_response_mismatch','The gateway error belongs to a different sport or provider.'));if(body?.diagnostic?.code&&typeof body.diagnostic.message==='string')return unavailable({...body.diagnostic,checkedAt:new Date().toISOString()});return unavailable(bridgeDiagnostic(response.status===401||response.status===403?'bridge_authentication_failed':'bridge_unavailable','The secure Render data bridge could not complete this request.',{httpStatus:response.status,retryable:response.status>=500,requiresOperator:response.status<500}));}
  if(body?.provider!=='BALLDONTLIE'||body.sport!=='NFL'||!['available','partial','unavailable','configured'].includes(body.status)||typeof body.diagnostic?.code!=='string'||typeof body.diagnostic?.message!=='string')return unavailable(bridgeDiagnostic('source_response_mismatch','The gateway returned a different provider, sport or unsupported dataset.'));
  if(body.items!==undefined&&(!Array.isArray(body.items)||body.items.length>30000)||body.records!==undefined&&(!Array.isArray(body.records)||body.records.length>10000))return unavailable(bridgeDiagnostic('unsupported_response','The NFL dataset exceeds its bounded shape.'));
  if(Array.isArray(body.items)&&body.items.some((row:any)=>row?.provider!=='BALLDONTLIE'||row.sport!=='NFL'||row.dataFamily!=='sportsbook_reference'||row.draftKingsPredictionsEquivalent!==false||row.executionVerified!==false||row.quotedAt!==null))return unavailable(bridgeDiagnostic('source_family_mismatch','Sportsbook references cannot be interpreted as native DraftKings Predictions contracts.'));
  return body as BdlResponse;
 }catch(error){const name=error instanceof Error?error.name:'';return unavailable(bridgeDiagnostic(name==='TimeoutError'||name==='AbortError'?'bridge_timeout':'bridge_network_error','A verified response from the Render data gateway is unavailable.',{retryable:true}));}
}
