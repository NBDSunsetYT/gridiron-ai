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
 if(process.env.GRIDIRON_CLOUD_ONLY==='1'&&process.env.GRIDIRON_AUTO_PROPS!=='0'){
  const {sharedCache,putCache}=await import('./public-nfl/store');
  await Promise.allSettled((['NFL','CFB'] as const).map(async sport=>{const key='automatic-prop-pagination:'+sport,row=await sharedCache('status',key),cursor=Number.isSafeInteger(row?.data.cursor)?row!.data.cursor:0,board=await freeProps(sport,cursor);await putCache('status',key,{cursor:board.nextCursor??0},sport,86400000);}));
  await(await import('./probability/automatic-props')).drainAutomaticProps(3).catch(()=>{});
 }

 return operations.map((operation,index)=>{
  const result=values[index];return{sport:operation.sport,task:operation.task,checkedAt,status:result.status==='fulfilled'?safeStatus(result.value):'failed',message:result.status==='fulfilled'?'Source status refreshed; provider access, coverage and persistence remain subject to their reported limitations.':'This source refresh could not be verified. Existing research and personal records remain preserved.'};
 });
}
