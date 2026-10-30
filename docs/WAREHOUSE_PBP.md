# Owner-authenticated play-by-play warehouse import

This CLI writes actual normalized historical plays to Supabase's relational `nfl_plays` table. It uses a verified user's access JWT, a publishable key and row-level security. It never needs a service-role key or a database password. Existing financial data is unrelated and is not changed.

## Prepare actual evidence

1. Sync the relevant season through the app's warehouse screen first. Referenced games and teams must already exist in your signed-in account.
2. Normalize a legally usable local nflverse CSV/GZ with `python -m modeling.nflverse_adapter source.csv.gz --max-week 18 --out normalized.csv`. Keep its source/provenance report. The normalizer's exclusions remain material; a normalized file is not every possible NFL play.
3. Optional `passer_name`, `receiver_name`, `rusher_name` and corresponding `_position` columns can preserve actual source identities. Otherwise the actual GSIS external ID is retained, the name is explicitly **Name unavailable**, and position is null. Passing on a play does not prove the player's roster position.
4. Keep source `played_at` timestamps with timezone. Provide `available_at` only when its historical availability is actually known. Missing EPA/success remains null, and missing historical publication time remains null.

## Authenticate privately

Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in your trusted environment. Obtain a current access token for your own confirmed Supabase user through the authorized sign-in flow. Do not put it in a command argument, source file, public URL, screenshot or log.

The CLI accepts `SUPABASE_USER_JWT`, a private file named by `--token-file`, or a hidden terminal prompt. Token files must have mode `0600` or stricter on Unix. Expired/revoked tokens are rejected normally; the CLI never invents a JWT or falls back to privileged credentials.

```sh
python scripts/import-pbp-supabase.py normalized.csv \
  --source 'Actual source URL, license and collection citation' \
  --token-file /your/private/current-user-token.txt \
  --chunk-size 200 --dry-run

python scripts/import-pbp-supabase.py normalized.csv \
  --source 'Actual source URL, license and collection citation' \
  --token-file /your/private/current-user-token.txt \
  --chunk-size 200 --report import-report.json
```

## Integrity and limits

- Every game/team/player lookup is scoped to the authenticated user's actual ID. Foreign keys also enforce ownership.
- All rows are mapped/validated before any player or play inserts. The schema preserves linked passer/receiver/rusher identities and actual game references.
- Each play includes source URL/citation, collection time, actual event time, availability or null, SHA-256 source version, and reliability status.
- Batches contain at most 500 rows. Files are bounded to 25 MB/100,000 plays. Use explicit partitions rather than silently truncating data.
- Inserts use `ON CONFLICT DO NOTHING`, never UPDATE. An identical retry inserts zero new plays. Existing immutable versions are retained even if the supplied file has changed; review corrections instead of assuming a second import overwrites history.
- Multi-request network imports are not one global PostgreSQL transaction. Completed batches remain if a later request fails. Deterministic external identities and ignore-duplicate inserts make retry safe.
- This pipeline does not manufacture injuries, player usage, routes, snap counts, historical availability, or calibration evidence. A stored historical event is not automatically valid point-in-time training evidence.

The executed single-game NFL import and repeat/readback counts are recorded in `docs/reports/v4-warehouse-live.json`. Tests with synthetic transports are separate mechanical checks.
