-- Read-only, owner-scoped export with the legacy v2 financial field names.
create function gridiron_private.export_financial() returns jsonb language plpgsql security definer set search_path='' as $$declare u uuid:=gridiron_private.owner_id();answer jsonb;begin
select jsonb_build_object(
 'journal',(select coalesce(jsonb_agg(jsonb_build_object('id',e.id,'user_id',e.user_id,'type',e.type,'sportsbook',a.sportsbook,'amount_cents',e.amount_cents,'date',e.occurred_at,'note',e.note,'reference',e.reference,'related_id',e.related_id,'reverses_id',e.reverses_id,'created_at',e.created_at) order by e.occurred_at,e.created_at),'[]'::jsonb) from public.ledger_entries e join public.sportsbook_accounts a on a.id=e.account_id and a.user_id=u where e.user_id=u),
 'postings',(select coalesce(jsonb_agg(jsonb_build_object('id',p.id,'journal_id',p.entry_id,'account',p.bucket,'sportsbook',a.sportsbook,'amount_cents',p.amount_cents)),'[]'::jsonb) from public.ledger_postings p join public.sportsbook_accounts a on a.id=p.account_id and a.user_id=u where p.user_id=u),
 'bets',(select coalesce(jsonb_agg(jsonb_build_object('id',b.id,'user_id',b.user_id,'sportsbook',a.sportsbook,'event',b.event,'market',b.market,'selection',b.selection,'odds',b.odds,'stake_cents',b.stake_cents,'placed_at',b.placed_at,'settled_at',b.settled_at,'result',b.result,'payout_cents',b.payout_cents,'notes',b.notes,'prediction',b.prediction,'legs',b.legs,'created_at',b.created_at) order by b.placed_at),'[]'::jsonb) from public.wagers b join public.sportsbook_accounts a on a.id=b.account_id and a.user_id=u where b.user_id=u),
 'audit',(select coalesce(jsonb_agg(jsonb_build_object('id',a.id,'user_id',a.user_id,'action',a.action,'entity_id',a.entity_id,'detail',a.detail,'created_at',a.created_at) order by a.created_at),'[]'::jsonb) from public.audit_log a where a.user_id=u)
) into answer;return answer;end$$;
create function public.gridiron_export_financial() returns jsonb language sql security invoker set search_path='' as $$select gridiron_private.export_financial()$$;
revoke all on function gridiron_private.export_financial() from public,anon,authenticated;
grant execute on function gridiron_private.export_financial() to authenticated;
revoke all on function public.gridiron_export_financial() from public,anon;
grant execute on function public.gridiron_export_financial() to authenticated;
