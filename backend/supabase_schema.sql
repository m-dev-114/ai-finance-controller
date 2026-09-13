-- Reference schema for Supabase/Postgres.
-- Note: the FastAPI app also auto-creates these tables on startup via
-- SQLAlchemy (Base.metadata.create_all), so running this manually is
-- optional — useful if you want the tables to exist before first boot,
-- or want to review the exact shape of the data model.

create table if not exists transactions (
    id text primary key,
    customer_id text not null,
    amount double precision not null,
    fee double precision not null default 0,
    tax double precision not null default 0,
    currency text default 'INR',
    status text default 'captured',
    created_at timestamp default now(),
    settlement_item_id text
);

create table if not exists settlement_batches (
    id text primary key,
    settlement_date timestamp not null,
    batch_amount double precision not null,
    currency text default 'INR'
);

create table if not exists settlement_items (
    id text primary key,
    batch_id text references settlement_batches(id),
    transaction_id text,
    net_amount double precision not null
);

create table if not exists bank_statement_lines (
    id text primary key,
    value_date timestamp not null,
    amount double precision not null,
    utr_reference text,
    narrative text,
    matched_batch_id text
);

create table if not exists ledger_entries (
    id text primary key,
    transaction_id text,
    entry_type text default 'revenue',
    amount double precision not null,
    recognized_date timestamp not null,
    matched_settlement_item_id text
);

create table if not exists reconciliation_runs (
    id text primary key,
    started_at timestamp default now(),
    finished_at timestamp,
    status text default 'running',
    stats jsonb default '{}'::jsonb
);

create table if not exists exceptions (
    id text primary key,
    run_id text references reconciliation_runs(id),
    level text not null,
    reference_ids jsonb default '[]'::jsonb,
    status text default 'open',
    confidence double precision,
    hypothesis text,
    reasoning_trail jsonb default '[]'::jsonb,
    amount_delta double precision,
    created_at timestamp default now(),
    resolved_at timestamp,
    resolved_by text
);

create table if not exists audit_log (
    id text primary key,
    exception_id text references exceptions(id),
    run_id text,
    actor text not null,
    action text not null,
    detail text,
    data_snapshot jsonb default '{}'::jsonb,
    created_at timestamp default now()
);

create index if not exists idx_exceptions_status on exceptions(status);
create index if not exists idx_exceptions_run on exceptions(run_id);
create index if not exists idx_audit_exception on audit_log(exception_id);
create index if not exists idx_settlement_items_batch on settlement_items(batch_id);
create index if not exists idx_settlement_items_txn on settlement_items(transaction_id);
