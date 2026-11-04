import {ApiError} from '../auth';
import {BACKUP_EXPANDED_LIMIT} from '../backups';
import {decodeCloudData} from './codec';
import {cloudError,requireCloudUser,type CloudContext} from './context';
/** Constant allow-list: authentication tables and server secrets are never exportable here. */
export const OWNED_TYPED_EXPORT_TABLES=[
 'profiles','preferences','notification_settings','sportsbook_accounts','ledger_entries','ledger_postings','wagers','wager_legs','settlements','reconciliation_records','audit_log','data_imports','watchlists','saved_research',
 'nfl_seasons','nfl_teams','nfl_players','nfl_games','nfl_plays','team_statistics','player_statistics','player_usage','depth_charts','coaching_tendencies','injury_reports','weather_reports',
 'market_providers','market_events','market_contracts','contract_quotes','contract_outcomes','model_versions','feature_snapshots','training_runs','simulation_runs','simulation_scenarios','probability_distributions','model_predictions','backtests','calibration_metrics','prediction_audits','saved_reports','paper_positions','cfb_simulation_runs','cfb_prediction_snapshots','research_workspaces','research_workspace_versions','probability_history'
] as const;
export async function exportOwnedTables(ctx:CloudContext,tables:readonly string[],maxBytes=BACKUP_EXPANDED_LIMIT){
 const user=requireCloudUser(ctx),allowed=new Set<string>([...OWNED_TYPED_EXPORT_TABLES,'gridiron_records','conversations','conversation_messages']),result:Record<string,Record<string,any>[] >={};let totalBytes=0;
 for(const table of tables){
  if(!allowed.has(table))throw new ApiError('The requested table is not part of an account export.');
  const order=table==='research_workspace_versions'?'workspace_id':table==='preferences'?'key':['profiles','notification_settings'].includes(table)?'user_id':'id';result[table]=[];let offset=0,expected:number|null=null;
  for(;;){
   let query=ctx.client.from(table).select('*',{count:'exact'}).eq('user_id',user.id).order(order);if(table==='research_workspace_versions')query=query.order('revision');const {data,error,count}=await query.range(offset,offset+999);
   if(error)cloudError(error);const page=data??[];
   if(typeof count!=='number')throw new ApiError('A complete export count could not be verified. No truncated archive was returned.',503);
   if(expected===null)expected=count;else if(count!==expected)throw new ApiError('Account records changed during export. Retry or use a consistent project-level backup.',409);
   totalBytes+=JSON.stringify(page).length;if(totalBytes>maxBytes)throw new ApiError('The complete account export exceeds 160 MB. Use a project-level backup or bounded source archives. No partial export was reported as complete.',413);
   result[table].push(...page);offset+=page.length;
   if(offset===expected)break;
   if(!page.length||offset>expected)throw new ApiError('Export pagination could not reconcile every owned row. Retry before relying on this archive.',409);
  }
 }
 return result;
}

/** Portable records contain complete decoded evidence and its original receipt.
 * The receipt is metadata, not a credential, and must survive archive recovery. */
export function portableCloudRecord(stored:Record<string,any>){
 const row:Record<string,any>={...stored,data:decodeCloudData(stored.data)};let kind=row.kind,value:any={...row};
 if(kind.startsWith('research_records/')){kind='research_records';value.kind=row.kind.slice('research_records/'.length);value.data=row.data?._recordFormat==='saved-research-v1'?row.data.value:row.data;}
 else if(kind==='simulation_jobs'){value={...row,...row.data,data:row.data.data,result:row.data.result,status:row.data.status,kind:row.data.kind};}
 else if(kind==='simulation_inputs'){value={...row,job_id:row.data.jobId,data:row.data.input,...(row.data.inputProof===undefined?{}:{inputProof:row.data.inputProof})};}
 return{kind,value};
}
