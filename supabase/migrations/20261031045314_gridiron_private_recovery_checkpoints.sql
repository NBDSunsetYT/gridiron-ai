-- Operator-only encrypted recovery artifacts. No user-facing or public API grant.
-- Encryption keys are generated outside the database and never stored here.
create table gridiron_shared_private.recovery_checkpoints (
 id uuid primary key default gen_random_uuid(),
 archive_id uuid not null,
 ordinal integer not null check(ordinal>=0),
 created_at timestamptz not null default clock_timestamp(),
 ciphertext bytea not null check(octet_length(ciphertext) between 128 and 33554432),
 row_counts jsonb not null check(jsonb_typeof(row_counts)='object'),
 plaintext_bytes bigint not null check(plaintext_bytes>0),
 sha256 text not null check(sha256 ~ '^[a-f0-9]{64}$'),
 unique(archive_id,ordinal)
);
alter table gridiron_shared_private.recovery_checkpoints enable row level security;
revoke all on gridiron_shared_private.recovery_checkpoints from public,anon,authenticated;
comment on table gridiron_shared_private.recovery_checkpoints is 'Operator-only AES-256 PGP row checkpoints; independent keys remain outside the database. Not a complete provider Auth/Storage/PITR backup.';
