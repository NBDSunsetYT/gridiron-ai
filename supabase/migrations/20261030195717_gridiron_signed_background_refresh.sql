-- Managed pg_net queue tables may be readable to database-login roles despite
-- caller REVOKE statements, because their managed owner controls the grants.
-- Queue only a one-use, short-lived request MAC; never the durable capability.
create or replace function gridiron_shared_private.public_refresh_tick() returns bigint
language plpgsql security definer set search_path=''
as $$declare capability text; request_id bigint; sent_at text; nonce text; signature text; begin
 select decrypted_secret into capability from vault.decrypted_secrets
  where name='gridiron_v5_public_refresh' limit 1;
 if capability is null or length(capability)<40 then
  raise exception 'Public research refresh capability is not provisioned'; end if;
 sent_at:=floor(extract(epoch from clock_timestamp())*1000)::bigint::text;
 nonce:=gen_random_uuid()::text;
 signature:=encode(extensions.hmac(convert_to('GRIDIRON-REFRESH-V1'||chr(10)||sent_at||chr(10)||nonce||chr(10)||'POST'||chr(10)||'/api/nfl/refresh','UTF8'),convert_to(capability,'UTF8'),'sha256'),'hex');
 select net.http_post(
  url:='https://gridiron-ai-gray.vercel.app/api/nfl/refresh',
  headers:=jsonb_build_object('Content-Type','application/json','X-Gridiron-Timestamp',sent_at,'X-Gridiron-Nonce',nonce,'X-Gridiron-Signature',signature),
  body:=jsonb_build_object('trigger','scheduled'),timeout_milliseconds:=30000
 ) into request_id;
 return request_id;
end $$;
revoke all on function gridiron_shared_private.public_refresh_tick() from public,anon,authenticated;
