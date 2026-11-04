import {ApiError} from '../auth';
export type EvidenceState='loading_research'|'resolving_player'|'preparing_simulation'|'simulation_running'|'calculating_probability'|'ready'|'data_delayed'|'source_unavailable'|'simulation_failed';
export function evidenceFailure(error:unknown){
 const message=error instanceof ApiError?error.message:'The research service could not complete this request. Existing evidence remains preserved.';
 if(error instanceof ApiError&&error.status===429)return{state:'data_delayed' as const,reasonCode:'compute_capacity_reached',reason:message,retryable:true,retryAt:new Date(new Date().setUTCHours(24,0,0,0)).toISOString()};
 if(error instanceof ApiError&&error.status===409)return{state:'simulation_running' as const,reasonCode:'simulation_already_running',reason:message,retryable:true,retryAfterSeconds:5};
 if(error instanceof Error&&(/timeout|aborted/i.test(error.name)||/timed out/i.test(error.message)))return{state:'data_delayed' as const,reasonCode:'source_timeout',reason:'The source or simulation worker timed out. Retry Analysis can resume this request.',retryable:true};
 return{state:'source_unavailable' as const,reasonCode:error instanceof ApiError&&error.status===422?'unsupported_evidence':'research_service_unavailable',reason:message,retryable:!(error instanceof ApiError&&[400,404,422].includes(error.status))};
}
