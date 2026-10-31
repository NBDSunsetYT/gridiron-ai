-- Extend the existing immutable research warehouse to team/game contracts.
-- No historical row, private policy, ledger, user or prediction is reset.
alter table public.shared_prop_contracts drop constraint shared_prop_contracts_stat_check;
alter table public.shared_prop_contracts add constraint shared_prop_contracts_stat_check
 check(stat in ('passingYards','passingTouchdowns','passingAttempts','completions','interceptions','rushingYards','carries','receivingYards','receptions','touchdowns','rushingTouchdowns','receivingTouchdowns','targets','gameWinner','spread','totalPoints','teamTotal'));
alter table public.shared_prop_contracts add constraint shared_prop_contracts_game_subject_check
 check(stat not in ('gameWinner','spread','totalPoints','teamTotal') or player_id is null);

alter table public.shared_prop_snapshots drop constraint shared_prop_snapshots_check4;
alter table public.shared_prop_snapshots add constraint shared_prop_snapshots_model_evidence_check
 check(raw_probability is null or (
  model_version is not null and input_version is not null and simulation_id is not null and
  ((category in ('gameWinner','spread','totalPoints','teamTotal') and player_id is null) or
   (category not in ('gameWinner','spread','totalPoints','teamTotal') and player_id is not null))
 ));

-- Unexposed operator boundary; callers receive no database-size information.
create function gridiron_shared_private.has_public_storage_headroom() returns boolean
language sql volatile security invoker set search_path=''
as $$select pg_database_size(current_database())<450000000$$;
revoke all on function gridiron_shared_private.has_public_storage_headroom() from public,anon,authenticated;

-- Keep the existing server capability, validation, immutable history and ACLs.
create or replace function gridiron_shared_private.prop_write_operation(token text,payload jsonb) returns jsonb
language plpgsql security definer set search_path=''
as $$declare
 action text:=payload->>'action';r public.shared_prop_runs;c public.shared_prop_contracts;q public.shared_prop_quotes;s public.shared_prop_snapshots;
 previous public.shared_prop_resolutions;existing_resolution public.shared_prop_resolutions;model public.shared_prop_model_artifacts;
 item jsonb;snapshot jsonb;contract jsonb;artifact jsonb;validation jsonb;output jsonb:='[]'::jsonb;
 raw numeric;calibrated numeric;captured timestamptz;starts timestamptz;at_time timestamptz;available timestamptz;
 model_id text;status_value text;previous_id text;run_value uuid;rank_value integer;model_category text;
begin
 if not gridiron_shared_private.valid_public_capability(token) then raise exception using errcode='42501',message='Server capability required';end if;
 if payload is null or jsonb_typeof(payload)<>'object' or octet_length(payload::text)>16000000 then raise exception 'Bounded player-prop JSON operation required' using errcode='22023';end if;
 if action in ('contract_put','snapshot_put') and not gridiron_shared_private.has_public_storage_headroom() then raise exception 'New public research is paused to preserve personal-record storage. Saved research and Wallet remain available; operator storage review required.' using errcode='54000';end if;
 if action='batch' then
  if jsonb_typeof(payload->'operations') is distinct from 'array' or jsonb_array_length(payload->'operations')>100 or jsonb_array_length(payload->'operations')<1 then raise exception 'Supply1–100 bounded non-nested research operations' using errcode='22023';end if;
  if exists(select 1 from jsonb_array_elements(payload->'operations') entry where jsonb_typeof(entry.value)<>'object' or entry.value->>'action'='batch') then raise exception 'Nested research batches are not supported' using errcode='22023';end if;
  for item in select value from jsonb_array_elements(payload->'operations') loop
   output:=output||jsonb_build_array(gridiron_shared_private.prop_write_operation(token,item));
  end loop;return output;
 elsif action='run_enqueue' then
  if jsonb_typeof(payload->'data') is distinct from 'object' or octet_length((payload->'data')::text)>8000000 then raise exception 'Bounded public research input required' using errcode='22023';end if;
  insert into public.shared_prop_runs(id,input_hash,data) values(coalesce(nullif(payload->>'id','')::uuid,gen_random_uuid()),payload->>'inputHash',payload->'data') on conflict(input_hash) do nothing;
  select * into r from public.shared_prop_runs where input_hash=payload->>'inputHash';return to_jsonb(r);
 elsif action='run_claim' then
  if nullif(payload->>'lease','') is null then raise exception 'A worker lease is required' using errcode='22023';end if;
  update public.shared_prop_runs set status='running',lease=(payload->>'lease')::uuid,error=null,updated_at=now()
   where id=(payload->>'id')::uuid and (status='queued' or status='running' and updated_at<now()-interval '4 minutes') returning * into r;
  if r.id is null then return null;end if;return to_jsonb(r);
 elsif action='run_checkpoint' then
  status_value:=payload->>'status';
  if status_value is null or status_value not in ('queued','completed','partial','unavailable','failed') then raise exception 'A valid research checkpoint status is required' using errcode='22023';end if;
  if payload?'data' and (jsonb_typeof(payload->'data')<>'object' or octet_length((payload->'data')::text)>8000000) then raise exception 'Bounded checkpoint data required' using errcode='22023';end if;
  if payload?'result' and payload->'result'<>'null'::jsonb and (jsonb_typeof(payload->'result')<>'object' or octet_length((payload->'result')::text)>8000000) then raise exception 'Bounded checkpoint result required' using errcode='22023';end if;
  update public.shared_prop_runs set status=status_value,lease=null,data=case when payload?'data' then payload->'data' else data end,
   result=case when payload?'result' then nullif(payload->'result','null'::jsonb) else result end,error=left(payload->>'error',2000),updated_at=now()
   where id=(payload->>'id')::uuid and status='running' and lease=(payload->>'lease')::uuid returning * into r;
  if r.id is null then raise exception 'Stale research worker lease' using errcode='40001';end if;return to_jsonb(r);
 elsif action='contract_put' then
  contract:=payload->'contract';
  if jsonb_typeof(contract) is distinct from 'object' or contract->>'sourceKind' not in ('authorized_feed','public_exchange') or contract->>'sourceKind' is null then raise exception 'Only authorized public contracts may enter shared research; manual records remain private' using errcode='22023';end if;
  if nullif(contract->>'contractId','') is null or nullif(contract->>'eventId','') is null or nullif(contract->>'gameId','') is null or nullif(contract->>'playerName','') is null or nullif(contract->>'rulesHash','') is null or contract->>'sourceUrl' is null or contract->>'sourceUrl' !~ '^https://[^[:space:]]+$' then raise exception 'Exact contract identity, rules and HTTPS provenance required' using errcode='22023';end if;
  if nullif(payload->>'definitionHash','') is null or nullif(payload->>'quoteHash','') is null or nullif(payload->>'quoteId','') is null then raise exception 'Immutable definition and quote identities required' using errcode='22023';end if;
  at_time:=(contract->>'observedAt')::timestamptz;
  if at_time is null or at_time>now()+interval '1 minute' then raise exception 'A nonfuture quote observation timestamp is required' using errcode='22023';end if;
  insert into public.shared_prop_contracts(id,provider,contract_id,event_id,game_id,player_id,player_name,stat,category,threshold,operator,event_start,definition_hash,data)
   values(contract->>'id',contract->>'provider',contract->>'contractId',contract->>'eventId',contract->>'gameId',nullif(contract->>'playerId',''),contract->>'playerName',contract->>'stat',contract->>'stat',(contract->>'threshold')::numeric,contract->>'operator',(contract->>'eventStart')::timestamptz,payload->>'definitionHash',contract)
   on conflict(id) do update set data=case when (excluded.data->>'observedAt')::timestamptz>=(shared_prop_contracts.data->>'observedAt')::timestamptz then excluded.data else shared_prop_contracts.data end,player_id=coalesce(excluded.player_id,shared_prop_contracts.player_id),player_name=excluded.player_name,updated_at=now()
   where shared_prop_contracts.definition_hash=excluded.definition_hash
    and shared_prop_contracts.provider=excluded.provider and shared_prop_contracts.contract_id=excluded.contract_id
    and shared_prop_contracts.event_id=excluded.event_id and shared_prop_contracts.game_id=excluded.game_id
    and shared_prop_contracts.stat=excluded.stat and shared_prop_contracts.threshold=excluded.threshold and shared_prop_contracts.operator=excluded.operator and shared_prop_contracts.event_start=excluded.event_start
    and shared_prop_contracts.data->>'rulesHash'=excluded.data->>'rulesHash'
    and (shared_prop_contracts.player_id is null or shared_prop_contracts.player_id=excluded.player_id)
   returning * into c;
  if c.id is null then raise exception 'Established player-prop contract definition cannot change' using errcode='22023';end if;
  insert into public.shared_prop_quotes(id,contract_id,quote_hash,quoted_at,observed_at,data)
   values(payload->>'quoteId',c.id,payload->>'quoteHash',nullif(contract->>'quotedAt','')::timestamptz,at_time,contract) on conflict do nothing;
  select * into q from public.shared_prop_quotes where contract_id=c.id and quote_hash=payload->>'quoteHash';
  if q.id is null then raise exception 'Quote identity is already associated with a different observation' using errcode='22023';end if;
  return to_jsonb(c)||jsonb_build_object('quoteId',q.id);
 elsif action='snapshot_put' then
  snapshot:=payload->'snapshot';contract:=snapshot->'contract';
  if jsonb_typeof(snapshot) is distinct from 'object' or jsonb_typeof(contract) is distinct from 'object' then raise exception 'A complete published research snapshot is required' using errcode='22023';end if;
  raw:=nullif(snapshot->'probability'->>'raw','')::numeric;calibrated:=nullif(snapshot->'probability'->>'calibrated','')::numeric;
  captured:=(snapshot->>'capturedAt')::timestamptz;starts:=(snapshot->'game'->>'startTime')::timestamptz;
  if raw is not null and (raw<0 or raw>1 or raw='NaN'::numeric) or calibrated is not null and (calibrated<0 or calibrated>1 or calibrated='NaN'::numeric) then raise exception 'Research probabilities must be finite and between zero and one' using errcode='22023';end if;
  select * into c from public.shared_prop_contracts where id=contract->>'id';
  select * into q from public.shared_prop_quotes where id=payload->>'quoteId';
  if c.id is null or q.id is null or q.contract_id<>c.id or c.game_id is distinct from snapshot->'game'->>'id' or c.event_start is distinct from starts or c.player_id is distinct from nullif(contract->>'playerId','') or c.player_id is distinct from nullif(snapshot->'player'->>'id','') or c.stat is distinct from contract->>'stat' or c.threshold is distinct from (contract->>'threshold')::numeric or c.operator is distinct from contract->>'operator' or c.data->>'rulesHash' is distinct from contract->>'rulesHash' then raise exception 'Snapshot game, player, threshold, rules and quote must match the verified contract' using errcode='22023';end if;
  select * into s from public.shared_prop_snapshots where id=snapshot->>'id';
  if s.id is not null then
   if s.contract_id is distinct from c.id or s.game_id is distinct from c.game_id or s.player_id is distinct from c.player_id or s.category is distinct from c.stat or s.side is distinct from snapshot->>'side' or s.raw_probability is distinct from raw or s.calibrated_probability is distinct from calibrated or s.model_version is distinct from nullif(snapshot->>'modelVersion','') or s.input_version is distinct from nullif(snapshot->>'inputVersion','') or s.simulation_id is distinct from nullif(snapshot->>'simulationId','')::uuid then raise exception 'Historical prediction identity cannot be reused for different model evidence' using errcode='22023';end if;
  else
   if captured is null or starts is null or captured>=starts or now()>=starts or captured>now()+interval '1 minute' then raise exception 'New predictions must be captured and archived before kickoff; retrospective probabilities are not accepted' using errcode='22023';end if;
   if raw is not null and not exists(select 1 from public.shared_nfl_jobs j where j.id=nullif(snapshot->>'simulationId','')::uuid and j.game_id=c.game_id and j.status='completed' and j.result->'result'->>'modelVersion'=snapshot->>'modelVersion' and (j.result->'result'->>'simulations')::integer=(snapshot->>'simulations')::integer and (snapshot->>'simulations')::integer>=10000) then raise exception 'Published probabilities require the matching completed full-game simulation' using errcode='22023';end if;
   model_id:=nullif(snapshot->'probability'->>'calibrationArtifactId','');
   if calibrated is not null and not exists(select 1 from public.shared_prop_model_artifacts a where a.id=model_id and a.status='approved' and a.model_version=snapshot->>'modelVersion' and a.category=c.stat and a.created_at<=captured) then raise exception 'Calibrated probabilities require a prior approved matching prop artifact' using errcode='22023';end if;
   insert into public.shared_prop_snapshots(id,run_id,contract_id,quote_id,simulation_id,game_id,player_id,player_name,category,side,threshold,operator,model_version,input_version,raw_probability,calibrated_probability,data_quality_score,mc_width,net_value_cents,calibration_artifact_id,calibration_status,captured_at,event_start,data)
    values(snapshot->>'id',(snapshot->>'runId')::uuid,c.id,q.id,nullif(snapshot->>'simulationId','')::uuid,c.game_id,c.player_id,coalesce(nullif(snapshot->'player'->>'name',''),c.player_name),c.stat,snapshot->>'side',c.threshold,c.operator,nullif(snapshot->>'modelVersion',''),nullif(snapshot->>'inputVersion',''),raw,calibrated,coalesce((snapshot->'dataQuality'->>'score')::integer,0),case when jsonb_typeof(snapshot->'probability'->'interval95')='array' then (snapshot->'probability'->'interval95'->>1)::numeric-(snapshot->'probability'->'interval95'->>0)::numeric else null end,nullif(snapshot->'valuation'->>'netValueCents','')::numeric,case when calibrated is not null then model_id else null end,case when calibrated is not null then 'approved' else null end,captured,starts,(snapshot-'contract'-'distribution')||jsonb_build_object('storageEncoding','nfl_market_snapshot_v7','contractRef',q.id,'contractOverlay',jsonb_build_object('playerId',contract->'playerId','liquidity',contract->'liquidity','position',contract->'position','subject',contract->'subject','mapping',contract->'mapping','verification',contract->'verification','observedAt',contract->'observedAt','quotedAt',contract->'quotedAt','sourceUpdatedAt',contract->'sourceUpdatedAt','quoteTimestampMeaning',contract->'quoteTimestampMeaning','displayedYesPercent',contract->'displayedYesPercent','displayedNoPercent',contract->'displayedNoPercent'))) returning * into s;
  end if;
  run_value:=coalesce(nullif(payload->>'runId','')::uuid,(snapshot->>'runId')::uuid);rank_value:=coalesce((payload->>'rank')::integer,0);
  insert into public.shared_prop_run_results(run_id,snapshot_id,rank) values(run_value,s.id,rank_value) on conflict(run_id,snapshot_id) do nothing;
  return to_jsonb(s);
 elsif action='run_link' then
  if jsonb_typeof(payload->'snapshotIds') is distinct from 'array' or jsonb_array_length(payload->'snapshotIds')>2000 then raise exception 'A bounded snapshot list is required' using errcode='22023';end if;
  run_value:=(payload->>'runId')::uuid;rank_value:=coalesce((payload->>'rankOffset')::integer,0);
  for item in select value from jsonb_array_elements(payload->'snapshotIds') loop
   insert into public.shared_prop_run_results(run_id,snapshot_id,rank) values(run_value,item#>>'{}',rank_value) on conflict(run_id,snapshot_id) do nothing;rank_value:=rank_value+1;
  end loop;return jsonb_build_object('linked',jsonb_array_length(payload->'snapshotIds'));
 elsif action='resolutions_put' then
  if jsonb_typeof(payload->'resolutions') is distinct from 'array' or jsonb_array_length(payload->'resolutions')>1000 then raise exception 'A bounded research-resolution batch is required' using errcode='22023';end if;
  for item in select value from jsonb_array_elements(payload->'resolutions') loop
   if jsonb_typeof(item)<>'object' or nullif(item->>'id','') is null or nullif(item->>'predictionId','') is null then raise exception 'Resolution identities are required' using errcode='22023';end if;
   perform pg_advisory_xact_lock(hashtextextended('gridiron_prop_resolution:'||(item->>'predictionId'),0));
   select * into s from public.shared_prop_snapshots where id=item->>'predictionId';
   if s.id is null then raise exception 'The frozen prediction is unavailable' using errcode='22023';end if;
   select * into existing_resolution from public.shared_prop_resolutions where id=item->>'id';
   if existing_resolution.id is not null then
    if existing_resolution.prediction_id is distinct from item->>'predictionId' or existing_resolution.status is distinct from item->>'status' or existing_resolution.source_version is distinct from item->>'sourceVersion' or existing_resolution.source_url is distinct from item->>'sourceUrl' or existing_resolution.observed_value is distinct from nullif(item->>'observedValue','')::numeric or existing_resolution.previous_resolution_id is distinct from nullif(item->>'previousResolutionId','') or existing_resolution.verified_final is distinct from coalesce((item->>'verifiedFinal')::boolean,false) then raise exception 'Resolution identity cannot rewrite an earlier outcome' using errcode='22023';end if;
    output:=output||jsonb_build_array(to_jsonb(existing_resolution));continue;
   end if;
   at_time:=(item->>'resolvedAt')::timestamptz;available:=coalesce(nullif(item->>'availableAt','')::timestamptz,at_time);status_value:=item->>'status';previous_id:=nullif(item->>'previousResolutionId','');
   if status_value is null or status_value not in ('yes','no','void','unresolved') or at_time is null or at_time>now()+interval '1 minute' or available is null or available>at_time or at_time<s.captured_at or status_value in ('yes','no') and available<s.event_start then raise exception 'A valid final research-resolution time and status are required' using errcode='22023';end if;
   if item->>'sourceUrl' is null or item->>'sourceUrl' !~ '^https://[^[:space:]]+$' or nullif(item->>'sourceVersion','') is null or item->>'rulesHash' is distinct from s.data->'contract'->>'rulesHash' then raise exception 'Final-source provenance and matching settlement rules are required' using errcode='22023';end if;
   select * into previous from public.shared_prop_resolutions where prediction_id=s.id order by created_at desc,resolved_at desc,id desc limit 1;
   if previous.id is not null and (previous_id is distinct from previous.id or at_time<=previous.resolved_at or previous.source_version=item->>'sourceVersion') or previous.id is null and previous_id is not null then raise exception 'Final-statistic corrections must append to the latest resolution with a new source version' using errcode='22023';end if;
   insert into public.shared_prop_resolutions(id,prediction_id,status,observed_value,resolved_at,available_at,source_url,source_version,verified_final,previous_resolution_id,data)
    values(item->>'id',s.id,status_value,nullif(item->>'observedValue','')::numeric,at_time,available,item->>'sourceUrl',item->>'sourceVersion',coalesce((item->>'verifiedFinal')::boolean,false),previous_id,item) returning * into existing_resolution;
   output:=output||jsonb_build_array(to_jsonb(existing_resolution));
  end loop;return output;
 elsif action='model_artifact_put' then
  artifact:=payload->'artifact';status_value:=artifact->>'status';model_id:=artifact->>'id';validation:=artifact->'validation';
  if jsonb_typeof(artifact) is distinct from 'object' or status_value is null or status_value not in ('candidate','approved') or artifact->>'protocol' is distinct from 'prop-prospective-game-block-6.0.0' or nullif(model_id,'') is null or nullif(artifact->>'category','') is null or nullif(artifact->>'modelVersion','') is null then raise exception 'A versioned calibration candidate or approved artifact is required' using errcode='22023';end if;
  select * into model from public.shared_prop_model_artifacts where id=model_id and status=status_value;
  if model.id is not null then if model.data is distinct from artifact then raise exception 'Model artifact versions are immutable' using errcode='22023';end if;return to_jsonb(model);end if;
  if status_value='candidate' then
   if nullif(artifact->>'createdAt','') is null or nullif(artifact->>'dataCutoff','') is null or nullif(artifact->>'trainingSampleSize','') is null or nullif(artifact->>'trainingGames','') is null or (artifact->>'createdAt')::timestamptz<now()-interval '1 minute' or (artifact->>'createdAt')::timestamptz>now()+interval '1 minute' or (artifact->>'dataCutoff')::timestamptz>(artifact->>'createdAt')::timestamptz or (artifact->>'trainingSampleSize')::integer<200 or (artifact->>'trainingGames')::integer<40 then raise exception 'Calibration candidates require current archival time and sufficient strictly prior prospective training data' using errcode='22023';end if;
  else
   select * into model from public.shared_prop_model_artifacts where id=model_id and status='candidate';
   if model.id is null or model.data-'status'-'validation' is distinct from artifact-'status'-'validation' or jsonb_typeof(validation) is distinct from 'object' or nullif(validation->>'id','') is null or nullif(validation->>'sampleSize','') is null or nullif(validation->>'games','') is null or nullif(validation->>'firstPredictionAt','') is null or nullif(validation->>'lastEventAt','') is null or nullif(validation->>'validatedAt','') is null or (validation->>'sampleSize')::integer<100 or (validation->>'games')::integer<20 or (validation->>'firstPredictionAt')::timestamptz<=model.created_at or (validation->>'lastEventAt')::timestamptz<(validation->>'firstPredictionAt')::timestamptz or (validation->>'validatedAt')::timestamptz<(validation->>'lastEventAt')::timestamptz or (validation->>'validatedAt')::timestamptz>now()+interval '1 minute' or jsonb_typeof(validation->'brierDifferenceInterval95') is distinct from 'array' or jsonb_typeof(validation->'logLossDifferenceInterval95') is distinct from 'array' then raise exception 'Approval requires a previously archived unchanged candidate and sufficient subsequent prospective validation with established Brier and log-loss improvement' using errcode='22023';end if;
   if jsonb_array_length(validation->'brierDifferenceInterval95')<>2 or jsonb_array_length(validation->'logLossDifferenceInterval95')<>2 or jsonb_typeof(validation->'brierDifferenceInterval95'->0) is distinct from 'number' or jsonb_typeof(validation->'brierDifferenceInterval95'->1) is distinct from 'number' or jsonb_typeof(validation->'logLossDifferenceInterval95'->0) is distinct from 'number' or jsonb_typeof(validation->'logLossDifferenceInterval95'->1) is distinct from 'number' or (validation->'brierDifferenceInterval95'->>0)::numeric>(validation->'brierDifferenceInterval95'->>1)::numeric or (validation->'logLossDifferenceInterval95'->>0)::numeric>(validation->'logLossDifferenceInterval95'->>1)::numeric or (validation->'brierDifferenceInterval95'->>1)::numeric>=0 or (validation->'logLossDifferenceInterval95'->>1)::numeric>=0 then raise exception 'Both paired improvement intervals must be finite, ordered and strictly below zero' using errcode='22023';end if;
  end if;
  insert into public.shared_prop_model_artifacts(id,status,category,model_version,method,data_cutoff,data) values(model_id,status_value,artifact->>'category',artifact->>'modelVersion',artifact->>'method',(artifact->>'dataCutoff')::timestamptz,artifact) returning * into model;
  return to_jsonb(model);
 else raise exception 'Unsupported player-prop research operation' using errcode='22023';end if;
end$$;

-- Preserve the existing bounded compute pool and fenced worker lifecycle.
-- Existing cached enqueue requests and small cache/status/failure writes remain usable.
do $capacity$
declare body text; needle text:=$needle$ if action='cache_put' then$needle$;
begin
 body:=pg_get_functiondef('gridiron_shared_private.write_operation_v1(text,jsonb)'::regprocedure);
 if position(needle in body)=0 or position('valid_public_capability(token)' in body)=0 then raise exception 'Unexpected shared worker implementation; no existing record was changed';end if;
 body:=replace(body,needle,$guard$ if action in ('job_enqueue','job_complete') and not gridiron_shared_private.has_public_storage_headroom() then
  if action='job_complete' or not exists(select 1 from public.shared_nfl_jobs where game_id=payload->>'gameId' and input_hash=payload->>'inputHash') then
   raise exception 'New public research is paused to preserve personal-record storage. Saved research and Wallet remain available; operator storage review required.' using errcode='54000';
  end if;
 end if;
$guard$||needle);
 execute body;
end $capacity$;

-- Public football data only. All underlying tables retain their existing RLS.
create or replace function public.gridiron_nfl_research_page(p_run_id uuid,p_filter jsonb default '{}'::jsonb)
returns jsonb language plpgsql stable security invoker set search_path=''
as $function$
declare f jsonb:=coalesce(p_filter,'{}'::jsonb); scope_value text; ranking_value text; provider_value text;
 offset_value integer; limit_value integer; min_quality numeric; result jsonb;
begin
 if jsonb_typeof(f) is distinct from 'object' or exists(select 1 from jsonb_object_keys(f) k where k not in ('scope','ranking','provider','category','gameId','side','search','cursor','limit','minQuality')) then raise exception 'Unsupported research page filters' using errcode='22023';end if;
 scope_value:=coalesce(f->>'scope','all');ranking_value:=coalesce(f->>'ranking','coverage');provider_value:=nullif(f->>'provider','');
 if scope_value not in ('all','player','game') or ranking_value not in ('coverage','calibrated','disagreement','reliability','uncertainty','injury','movement') or provider_value is not null and provider_value not in ('DraftKings Predictions','Kalshi') then raise exception 'Unsupported research scope, ranking or provider' using errcode='22023';end if;
 if f?'side' and (jsonb_typeof(f->'side') is distinct from 'string' or f->>'side' not in ('YES','NO')) or length(coalesce(f->>'search',''))>80 or f?'cursor' and coalesce(f->>'cursor','')!~'^[0-9]{1,6}$' or f?'limit' and coalesce(f->>'limit','')!~'^[0-9]{1,3}$' or f?'minQuality' and coalesce(f->>'minQuality','')!~'^[0-9]{1,3}(\.[0-9]{1,6})?$' then raise exception 'Invalid research page values' using errcode='22023';end if;
 if exists(select 1 from jsonb_each(f) x where x.key in ('scope','ranking','provider','category','gameId','search') and jsonb_typeof(x.value) is distinct from 'string') then raise exception 'Research labels must be strings' using errcode='22023';end if;
 if f?'category' and f->>'category' not in ('passingYards','passingTouchdowns','passingAttempts','completions','interceptions','rushingYards','carries','receivingYards','receptions','touchdowns','rushingTouchdowns','receivingTouchdowns','targets','gameWinner','spread','totalPoints','teamTotal') or f?'gameId' and length(f->>'gameId') not between 1 and 200 then raise exception 'Unsupported research category or game' using errcode='22023';end if;
 offset_value:=coalesce((f->>'cursor')::integer,0);limit_value:=coalesce((f->>'limit')::integer,60);min_quality:=coalesce((f->>'minQuality')::numeric,0);
 if offset_value>100000 or limit_value<1 or limit_value>80 or min_quality<0 or min_quality>100 then raise exception 'Research page exceeds its bounded range' using errcode='22023';end if;
 with base as materialized (
  select s.id,r.rank,s.raw_probability,s.calibrated_probability,s.side,s.data_quality_score,
   case when ranking_value='reliability' and jsonb_typeof(s.data#>'{probability,historicalSampleSize}')='number' then (s.data#>>'{probability,historicalSampleSize}')::numeric end as history_n,
   case when ranking_value='uncertainty' and jsonb_typeof(s.data#>'{probability,modelInterval95}')='array' and jsonb_array_length(s.data#>'{probability,modelInterval95}')=2
     and jsonb_typeof(s.data#>'{probability,modelInterval95,0}')='number' and jsonb_typeof(s.data#>'{probability,modelInterval95,1}')='number'
    then (s.data#>>'{probability,modelInterval95,1}')::numeric-(s.data#>>'{probability,modelInterval95,0}')::numeric end as model_width,
   case when ranking_value='injury' and jsonb_typeof(s.data#>'{sensitivity,injuryDelta}')='number' then abs((s.data#>>'{sensitivity,injuryDelta}')::numeric) end as injury_delta,
   case when ranking_value in('disagreement','movement') and (case when s.side='YES' then c.data->>'yesAskCents' else c.data->>'noAskCents' end) ~ '^[0-9]+(\.[0-9]+)?$'
    then (case when s.side='YES' then c.data->>'yesAskCents' else c.data->>'noAskCents' end)::numeric end as current_ask,
   case when ranking_value='movement' and (case when s.side='YES' then opening.data->>'yesAskCents' else opening.data->>'noAskCents' end) ~ '^[0-9]+(\.[0-9]+)?$'
    then (case when s.side='YES' then opening.data->>'yesAskCents' else opening.data->>'noAskCents' end)::numeric end as opening_ask,
   coalesce(ranking_value in('disagreement','movement') and (c.data#>>'{verification,current}')='true' and (c.data#>>'{verification,quoteVerified}')='true' and c.data->>'sourceKind'<>'manual_verified'
    and coalesce(nullif(c.data->>'quotedAt','')::timestamptz,(c.data->>'observedAt')::timestamptz) between now()-interval '120 seconds' and now()+interval '1 minute'
    and c.event_start>now(),false) as quote_current,
   coalesce(ranking_value not in('coverage','movement') and j.status='completed' and j.input_hash=cache.input_hash and cache.data->>'inputVerified'='true' and cache.data->>'pipelineVersion'='public-nfl-7.0.0' and cache.updated_at between now()-interval '30 minutes' and now()+interval '1 minute'
    and s.event_start>now(),false) as model_current,
   opening.observed_at as opening_at,latest.observed_at as latest_at
  from public.shared_prop_run_results r
   join public.shared_prop_snapshots s on s.id=r.snapshot_id
   join public.shared_prop_contracts c on c.id=s.contract_id
   left join public.shared_nfl_jobs j on ranking_value not in('coverage','movement') and j.id=s.simulation_id
   left join public.shared_nfl_cache cache on ranking_value not in('coverage','movement') and cache.kind='detail' and cache.key=s.game_id
   left join lateral(select q.data,q.observed_at from public.shared_prop_quotes q where ranking_value='movement' and q.contract_id=c.id and q.data#>>'{verification,quoteVerified}'='true' order by q.observed_at,q.id limit 1) opening on true
   left join lateral(select q.observed_at from public.shared_prop_quotes q where ranking_value='movement' and q.contract_id=c.id and q.data#>>'{verification,quoteVerified}'='true' order by q.observed_at desc,q.id desc limit 1) latest on true
  where r.run_id=p_run_id
   and (scope_value='all' or scope_value='game' and s.category in('gameWinner','spread','totalPoints','teamTotal') or scope_value='player' and s.category not in('gameWinner','spread','totalPoints','teamTotal'))
   and (provider_value is null or c.provider=provider_value)
   and (not(f?'category') or s.category=f->>'category') and (not(f?'gameId') or s.game_id=f->>'gameId') and (not(f?'side') or s.side=f->>'side')
   and (not(f?'search') or position(lower(f->>'search') in lower(s.player_name))>0) and s.data_quality_score>=min_quality
 ), metrics as materialized (
  select *,case when model_current then calibrated_probability end as calibrated_metric,
   case when model_current and quote_current and current_ask>0 and current_ask<100 then abs(coalesce(calibrated_probability,raw_probability)-current_ask/100) end as disagreement_metric,
   case when model_current and raw_probability is not null and history_n>0 then history_n end as reliability_metric,
   case when model_current and raw_probability is not null and model_width between 0 and 1 then model_width end as uncertainty_metric,
   case when model_current and raw_probability is not null and injury_delta between 0 and 1 then injury_delta end as injury_metric,
   case when quote_current and current_ask>0 and current_ask<100 and opening_ask>0 and opening_ask<100 and latest_at>opening_at then current_ask-opening_ask end as movement_metric
  from base
 ), ranked as materialized (
  select *,case ranking_value when 'calibrated' then calibrated_metric when 'disagreement' then disagreement_metric when 'reliability' then reliability_metric when 'uncertainty' then uncertainty_metric when 'injury' then injury_metric when 'movement' then abs(movement_metric) else rank end as metric
  from metrics
 ), eligible as materialized (select * from ranked where ranking_value='coverage' or metric is not null),
 page as (select * from eligible order by case when ranking_value='coverage' then rank end asc,
  case when ranking_value='uncertainty' then metric end asc nulls last,
  case when ranking_value not in('coverage','uncertainty') then metric end desc nulls last,id asc offset offset_value limit limit_value)
 select jsonb_build_object('rows',coalesce((select jsonb_agg((case when s.data->>'storageEncoding'='nfl_market_snapshot_v7' then s.data||jsonb_build_object('contract',captured_quote.data||coalesce(s.data->'contractOverlay','{}'::jsonb)) else s.data end)||jsonb_build_object('rankingMetrics',jsonb_build_object(
  'calibratedProbability',p.calibrated_metric,'modelMarketDifference',p.disagreement_metric,'historicalSupport',p.reliability_metric,
  'uncertaintyWidth',p.uncertainty_metric,'injuryChange',p.injury_metric,'priceChange',p.movement_metric)) order by case when ranking_value='coverage' then p.rank end asc,case when ranking_value='uncertainty' then p.metric end asc nulls last,case when ranking_value not in('coverage','uncertainty') then p.metric end desc nulls last,p.id asc)
  from page p join public.shared_prop_snapshots s on s.id=p.id join public.shared_prop_quotes captured_quote on captured_quote.id=s.quote_id),'[]'::jsonb),'total',(select count(*) from eligible),
  'nextCursor',case when offset_value+(select count(*) from page)<(select count(*) from eligible) then (offset_value+(select count(*) from page))::text else null end) into result;
 return result;
end $function$;
revoke all on function public.gridiron_nfl_research_page(uuid,jsonb) from public;
grant execute on function public.gridiron_nfl_research_page(uuid,jsonb) to anon,authenticated;
