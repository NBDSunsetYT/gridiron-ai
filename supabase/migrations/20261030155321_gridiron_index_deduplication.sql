-- Remove only redundant, non-constraint indexes with the same complete key,
-- predicate, expressions, collation and operator classes. Never drops a table,
-- constraint, unique/primary index, or an index with distinct coverage.
do $$
declare candidate record;begin
 for candidate in
 select i.indexrelid,ni.nspname,ci.relname
 from pg_index i
 join pg_class ci on ci.oid=i.indexrelid
 join pg_namespace ni on ni.oid=ci.relnamespace
 where ni.nspname='public' and not i.indisunique and not i.indisprimary
 and not exists(select 1 from pg_constraint c where c.conindid=i.indexrelid)
 and exists(
  select 1 from pg_index other_i join pg_class other_c on other_c.oid=other_i.indexrelid
  where other_i.indrelid=i.indrelid and other_i.indexrelid<>i.indexrelid
  and other_i.indisvalid and other_i.indisready
  and other_i.indkey=i.indkey and other_i.indclass=i.indclass
  and other_i.indcollation=i.indcollation and other_i.indoption=i.indoption
  and other_i.indexprs::text is not distinct from i.indexprs::text
  and other_i.indpred::text is not distinct from i.indpred::text
  and (other_i.indisunique
   or (case when other_c.relname like 'gridiron_fk_%' then 2 else 1 end)<(case when ci.relname like 'gridiron_fk_%' then 2 else 1 end)
   or ((case when other_c.relname like 'gridiron_fk_%' then 2 else 1 end)=(case when ci.relname like 'gridiron_fk_%' then 2 else 1 end) and other_i.indexrelid<i.indexrelid))
 )
 loop execute format('drop index %I.%I',candidate.nspname,candidate.relname);end loop;
end $$;
