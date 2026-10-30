-- Immutable private replay inputs for durable injury-driven simulation jobs.
-- Additive only: existing bankroll journals, bets and source snapshots are untouched.
CREATE TABLE simulation_inputs(
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id TEXT NOT NULL UNIQUE,
  data TEXT NOT NULL CHECK(json_valid(data)),
  created_at TEXT NOT NULL
);
CREATE INDEX simulation_inputs_owner ON simulation_inputs(user_id,job_id);
CREATE TRIGGER simulation_inputs_immutable BEFORE UPDATE ON simulation_inputs BEGIN SELECT RAISE(ABORT,'simulation input snapshots are immutable'); END;
PRAGMA user_version = 3;
