-- Outreach outcomes: the ground truth that calibrates prospecting priority.
-- Deliberately NO owner name, phone, email or notes: parcel pin + outcome only.
create table if not exists outreach_exports (
  export_id        text primary key,            -- e.g. 20261024-0900
  exported_at      timestamptz not null default now(),
  list_sha256      text not null                -- hash of the exported CSV, so tier/priority at export is provable
);
create table if not exists outreach_outcomes (
  id               bigserial primary key,
  export_id        text not null references outreach_exports(export_id),
  county_pin       text not null,
  tier_at_export   text not null check (tier_at_export in ('A','B','C')),
  priority_at_export numeric not null,
  outcome          text not null check (outcome in
                   ('NOT_ATTEMPTED','NO_CONTACT','CONTACTED','NOT_INTERESTED','APPOINTMENT','BOOKED','DO_NOT_CONTACT')),
  outcome_at       timestamptz not null default now(),
  recorded_by      text not null,
  unique (export_id, county_pin)
);
alter table outreach_exports enable row level security;
alter table outreach_outcomes enable row level security;
-- Server-side service role only; no anon policy is created on purpose.
