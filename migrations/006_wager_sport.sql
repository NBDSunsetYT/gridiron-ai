-- Additive only. The initializer snapshots every existing database before
-- pending migrations. Existing wagers retain NULL: no sport is inferred.
ALTER TABLE bets ADD COLUMN sport TEXT CHECK(sport IN ('NFL','CFB'));
