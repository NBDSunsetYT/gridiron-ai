-- SQLite cannot relax NOT NULL in place. This transactionally copies every old
-- wager byte-for-byte, then swaps the table; initializeDatabase takes a verified
-- consistent backup before applying pending migrations to an existing database.
CREATE TABLE bets_v6 (
 id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 sportsbook TEXT NOT NULL,event TEXT NOT NULL,market TEXT NOT NULL,selection TEXT NOT NULL,
 odds INTEGER,stake_cents INTEGER NOT NULL,placed_at TEXT NOT NULL,settled_at TEXT,
 result TEXT NOT NULL DEFAULT 'pending',payout_cents INTEGER,notes TEXT NOT NULL DEFAULT '',
 prediction TEXT,legs TEXT,created_at TEXT NOT NULL,
 market_instrument TEXT NOT NULL DEFAULT 'sportsbook' CHECK(market_instrument IN ('sportsbook','event_contract')),
 player TEXT CHECK(player IS NULL OR length(player)<=180),
 contract_price_cents TEXT,contract_quantity INTEGER,entry_fee_cents INTEGER,
 CHECK((market_instrument='sportsbook' AND odds IS NOT NULL AND contract_price_cents IS NULL AND contract_quantity IS NULL AND entry_fee_cents IS NULL)
 OR (market_instrument='event_contract' AND odds IS NULL AND contract_price_cents IS NOT NULL))
);
INSERT INTO bets_v6(id,user_id,sportsbook,event,market,selection,odds,stake_cents,placed_at,settled_at,result,payout_cents,notes,prediction,legs,created_at)
 SELECT id,user_id,sportsbook,event,market,selection,odds,stake_cents,placed_at,settled_at,result,payout_cents,notes,prediction,legs,created_at FROM bets;
DROP TABLE bets;
ALTER TABLE bets_v6 RENAME TO bets;
CREATE INDEX bet_owner ON bets(user_id,placed_at);
PRAGMA user_version = 4;
