-- GateKeeper certification receipts and search tasks.
-- STAGED ONLY: apply after 004-006 in a provisioned Supabase project.
-- No production Supabase project existed during the October 19 investigation.
-- This DDL is not evidence that any issuer document or roof has been reviewed.
create extension if not exists pgcrypto;

create table if not exists public.aero_certification_tasks (
  task_id text primary key check(task_id ~ '^GK-[0-9a-f]{18}$'),
  territory_id text not null references public.aero_territories(id),
  property_id uuid not null references public.aero_property_identity(id),
  task_kind text not null,
  issuer_record_id text,
  source_url text not null check(source_url ~ '^https://'),
  source_mode text not null,
  status text not null default 'OPEN'
    check(status in ('OPEN','SOURCE_BLOCKED','AWAITING_AUTHORIZED_PROVIDER',
      'AWAITING_HUMAN_EVIDENCE','EVIDENCE_ATTACHED_PENDING_HUMAN_REVIEW','REVIEWED_NOT_RELEASED')),
  priority integer not null default 50 check(priority between 0 and 100),
  original_evidence_id uuid references public.aero_evidence_objects(id),
  evidence_requirements jsonb not null default '[]'::jsonb,
  next_eligible_at timestamptz,
  recorded_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists aero_certification_tasks_due_idx
  on public.aero_certification_tasks(next_eligible_at, priority);
create index if not exists aero_certification_tasks_parcel_idx
  on public.aero_certification_tasks(property_id,task_kind);

create table if not exists public.aero_certification_review_receipts (
  id uuid primary key default gen_random_uuid(),
  task_id text not null references public.aero_certification_tasks(task_id),
  property_id uuid not null references public.aero_property_identity(id),
  original_evidence_id uuid references public.aero_evidence_objects(id),
  issuer_record_id text,
  issuer_name text,
  issuer_document_sha256 text
    check(issuer_document_sha256 is null or issuer_document_sha256 ~ '^[0-9a-f]{64}$'),
  source_url text not null check(source_url ~ '^https://'),
  source_captured_at timestamptz not null,
  reviewer_id text not null check(length(btrim(reviewer_id)) >= 3),
  reviewer_role text not null,
  reviewed_at timestamptz not null,
  review_decision text not null
    check(review_decision in ('RECORD_EXAMINED_PENDING_SECOND_REVIEW','REJECTED_BAD_IDENTITY',
      'REJECTED_INSUFFICIENT_EVIDENCE','CONFIRMED_ISSUER_RECORD_NOT_FINAL_INSPECTION',
      'CONFIRMED_FINAL_INSPECTION_RECORD','SCOPE_UNDETERMINED')),
  final_inspection_outcome text not null default 'UNKNOWN'
    check(final_inspection_outcome in ('UNKNOWN','APPROVED','FAILED','NOT_APPLICABLE')),
  review_notes text not null default '',
  recorded_at timestamptz not null default now(),
  unique(task_id, reviewer_id, reviewed_at),
  check(review_decision <> 'CONFIRMED_FINAL_INSPECTION_RECORD'
    or (issuer_document_sha256 is not null and issuer_record_id is not null
      and final_inspection_outcome <> 'UNKNOWN'))
);
create index if not exists aero_certification_receipts_task_idx
  on public.aero_certification_review_receipts(task_id, recorded_at desc);

create table if not exists public.aero_certification_release_events (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references public.aero_property_identity(id),
  territory_id text not null references public.aero_territories(id),
  decision text not null check(decision in ('DENIED','ON_HOLD','APPROVED','REVOKED')),
  rubric_version text not null,
  documented_inputs jsonb not null default '[]'::jsonb,
  reviewer_id text not null check(length(btrim(reviewer_id)) >= 3),
  approved_by text not null check(length(btrim(approved_by)) >= 3),
  source_receipt_ids uuid[] not null default '{}',
  reason text not null,
  occurred_at timestamptz not null default now(),
  check(decision <> 'APPROVED' or
    (cardinality(source_receipt_ids) >= 2 and length(reason) >= 20
     and reviewer_id <> approved_by))
);
create index if not exists aero_release_event_property_idx
  on public.aero_certification_release_events(property_id, occurred_at desc);

-- Hard append-only history for issuer review receipts and release decisions,
-- even if a privileged service path accidentally issues an UPDATE/DELETE.
create or replace function public.aero_block_certification_event_mutation()
returns trigger language plpgsql as $$
begin
  raise exception 'GateKeeper certification review/release receipts are append-only';
end;
$$;
drop trigger if exists aero_review_receipts_immutable on public.aero_certification_review_receipts;
create trigger aero_review_receipts_immutable
  before update or delete on public.aero_certification_review_receipts
  for each row execute function public.aero_block_certification_event_mutation();
drop trigger if exists aero_release_events_immutable on public.aero_certification_release_events;
create trigger aero_release_events_immutable
  before update or delete on public.aero_certification_release_events
  for each row execute function public.aero_block_certification_event_mutation();

alter table public.aero_certification_tasks enable row level security;
alter table public.aero_certification_review_receipts enable row level security;
alter table public.aero_certification_release_events enable row level security;
revoke all on public.aero_certification_tasks,
 public.aero_certification_review_receipts,
 public.aero_certification_release_events from anon,authenticated;
-- Use only a privileged backend service for controlled writes.
grant select,insert,update on public.aero_certification_tasks to service_role;
grant select,insert on public.aero_certification_review_receipts,
 public.aero_certification_release_events to service_role;
-- The service key must remain server-only; row-level security alone does not
-- prove a reviewer has approved evidence. That needs authenticated review flows
-- and independent checks before each APPROVED release-event insertion.
