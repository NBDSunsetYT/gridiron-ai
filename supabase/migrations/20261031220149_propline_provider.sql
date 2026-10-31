-- Existing public quote table/RLS/immutable history/storage guards remain intact.
-- Recovery: previous provider allowlist was BallDontLie, CollegeFootballData,
-- DraftKings Predictions, Kalshi. Reverting after PropLine writes requires an
-- operator-reviewed archive; never delete quotes or user records to roll back.
alter table public.provider_market_quotes drop constraint provider_market_quotes_provider_check;
alter table public.provider_market_quotes add constraint provider_market_quotes_provider_check
 check(provider in ('BallDontLie','CollegeFootballData','DraftKings Predictions','Kalshi','PropLine'));
alter table public.provider_market_quotes add constraint propline_sportsbook_family
 check(provider<>'PropLine' or market_family='sportsbook_reference');
