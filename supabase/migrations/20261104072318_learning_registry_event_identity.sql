-- Enforce cross-request idempotency even if two authorized workers race.
-- Existing forecasts, actuals, evaluations and private data are unchanged.
create unique index football_learning_registry_event_once
 on public.football_learning_records(kind,sport,model_version,(summary->>'candidateId'))
 where kind in ('promotion','rollback');
