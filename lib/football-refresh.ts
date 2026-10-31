/** Additional source refreshes share the existing authenticated operator clock.
 * Persist only bounded status metadata here; quotes, models and predictions
 * retain their own storage/compute admission and user-ownership boundaries. */
function safeStatus(value:unknown){const status=value&&typeof value==='object'?(value as any).status:null;return typeof status==='string'&&['completed','available','partial','unavailable','queued','running','blocked','paused_capacity','missing_credentials','render_backend_required','insufficient_evidence'].includes(status)?status:'unverified';}
export async function refreshAdditionalFootballResearch(){
 const checkedAt=new Date().toISOString();const {freeProps}=await import('./free-props-service');
 const operations=[
  {sport:'CFB',task:'college_sources',work:()=>import('./college-football/service').then(source=>source.refreshCollegeResearch())},
  {sport:'CFB',task:'sportsbook_reference',work:()=>freeProps('CFB')},
  {sport:'NFL',task:'sportsbook_reference',work:()=>freeProps('NFL')},
 ];
 const values=await Promise.allSettled(operations.map(operation=>operation.work()));
 return operations.map((operation,index)=>{
  const result=values[index];return{sport:operation.sport,task:operation.task,checkedAt,status:result.status==='fulfilled'?safeStatus(result.value):'failed',message:result.status==='fulfilled'?'Source status refreshed; provider access, coverage and persistence remain subject to their reported limitations.':'This source refresh could not be verified. Existing research and personal records remain preserved.'};
 });
}
