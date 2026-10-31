-- During a rolling upgrade, legacy writers keep their existing full format.
-- Only the v7 writer requests the new encoding, after full server validation.
-- No stored snapshot, quote, probability or private record is rewritten.
do $compatibility$
declare definition text; before_value text:=$before$(snapshot-'contract'-'distribution')||jsonb_build_object('storageEncoding','nfl_market_snapshot_v7','contractRef',q.id,'contractOverlay',jsonb_build_object('playerId',contract->'playerId','liquidity',contract->'liquidity','position',contract->'position','subject',contract->'subject','mapping',contract->'mapping','verification',contract->'verification','observedAt',contract->'observedAt','quotedAt',contract->'quotedAt','sourceUpdatedAt',contract->'sourceUpdatedAt','quoteTimestampMeaning',contract->'quoteTimestampMeaning','displayedYesPercent',contract->'displayedYesPercent','displayedNoPercent',contract->'displayedNoPercent'))$before$; after_value text; matches integer;
begin
 definition:=pg_get_functiondef('gridiron_shared_private.prop_write_operation(text,jsonb)'::regprocedure);
 matches:=(length(definition)-length(replace(definition,before_value,'')))/length(before_value);
 if matches<>1 or position('valid_public_capability(token)' in definition)=0 then raise exception 'Expected exact prior compact storage expression; historical records preserved';end if;
 after_value:='case when snapshot->>''storageRequest''=''nfl_market_snapshot_v7'' then '||before_value||' else snapshot end';
 execute replace(definition,before_value,after_value);
end $compatibility$;
