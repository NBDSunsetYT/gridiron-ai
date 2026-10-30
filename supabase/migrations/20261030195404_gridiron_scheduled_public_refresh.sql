-- Optional hosted extensions use existing database compute; no paid service is
-- provisioned. Embedded Postgres tests have no network scheduler and skip them.
do $$begin
 if exists(select 1 from pg_available_extensions where name='pg_cron') then
  execute 'create extension if not exists pg_cron with schema pg_catalog';
 end if;
 if exists(select 1 from pg_available_extensions where name='pg_net') then
  execute 'create extension if not exists pg_net with schema extensions';
  execute 'revoke all on schema net from public,anon,authenticated';
  execute 'revoke all on all tables in schema net from public,anon,authenticated';
  execute 'revoke all on all functions in schema net from public,anon,authenticated';
 end if;
end $$;

-- Callable only by the database owner/scheduler. The capability is provisioned
-- separately in encrypted Vault and is never embedded in migration/job text.
create function gridiron_shared_private.public_refresh_tick() returns bigint
language plpgsql security definer set search_path=''
as $$declare capability text; request_id bigint; begin
 select decrypted_secret into capability from vault.decrypted_secrets
  where name='gridiron_v5_public_refresh' limit 1;
 if capability is null or length(capability)<40 then
  raise exception 'Public research refresh capability is not provisioned'; end if;
 select net.http_post(
  url:='https://gridiron-ai-gray.vercel.app/api/nfl/refresh',
  headers:=jsonb_build_object('Content-Type','application/json','Authorization','Bearer '||capability),
  body:=jsonb_build_object('trigger','scheduled'),timeout_milliseconds:=30000
 ) into request_id;
 return request_id;
end $$;
revoke all on function gridiron_shared_private.public_refresh_tick() from public,anon,authenticated;
comment on function gridiron_shared_private.public_refresh_tick() is 'Owner-only automatic public NFL refresh. Call every15minutes with pg_cron; provision encrypted Vault capability separately. No personal data is accessed.';
