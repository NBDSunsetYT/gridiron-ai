import {ApiError} from '../auth';
export class ResearchStorageError extends ApiError{constructor(message:string,status:number,public code:string,public retryable:boolean){super(message,status);}}
export function researchStorageFailure(error:any):never{
 const code=String(error?.code??''),message=String(error?.message??'');
 if(code==='54000')throw new ResearchStorageError(/daily/i.test(message)?'Daily simulation capacity is reached. Saved research is unchanged.':'Research storage capacity is protected. Your draft remains queued; existing records are unchanged.',503,/daily/i.test(message)?'compute_capacity':'storage_capacity',true);
 if(['PGRST301','PGRST302','PGRST303','28000','28P01'].includes(code))throw new ResearchStorageError('Research authentication failed. Your draft was retained; reconnect your account or retry.',401,'authentication_failure',false);
 if(code==='42501')throw new ResearchStorageError('The research database denied this operation. Your draft was retained; permissions need repair.',403,'database_permission_failure',false);
 if(['42P01','42883','PGRST202','PGRST205'].includes(code))throw new ResearchStorageError('The research storage schema is not available to the API. Existing records were preserved.',503,'schema_mismatch',false);
 if(code==='57014'||/timeout|timed out|abort/i.test(message))throw new ResearchStorageError('The research storage request timed out. Your draft remains queued for retry.',504,'network_timeout',true);
 if(/^08/.test(code)||/fetch failed|network|connection/i.test(message))throw new ResearchStorageError('The research database could not be reached. Your draft remains queued for retry.',503,'backend_outage',true);
 throw new ResearchStorageError('Research storage is temporarily unavailable. Your draft remains queued; existing records were preserved.',503,'temporary_service_failure',true);
}
