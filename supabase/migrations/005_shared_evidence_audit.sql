-- Shared multi-territory evidence catalog with dedupe, provenance, and audit.
-- Apply in a configured Supabase project before server-side ingestion.
create extension if not exists pgcrypto;
create table if not exists public.aero_territories (
 id text primary key, display_name text not null, jurisdiction text not null,
 parent_id text references public.aero_territories(id), enabled boolean not null default true
);
insert into public.aero_territories(id,display_name,jurisdiction,parent_id)
values ('dakota-county','Dakota County','dakota_county',null),
 ('kings-wood-001','Kings Wood · Eagan','eagan','dakota-county'),
 ('burnsville-expansion','Burnsville Expansion','burnsville','dakota-county')
on conflict(id) do update set display_name=excluded.display_name,jurisdiction=excluded.jurisdiction,parent_id=excluded.parent_id;
create table if not exists public.aero_evidence_objects(
 id uuid primary key default gen_random_uuid(),
 source_key text not null, source_record_id text not null,
 canonical_url text, content_sha256 text, media_type text, byte_length bigint,
 source_published_at timestamptz, first_seen_at timestamptz not null default now(),
 last_checked_at timestamptz not null default now(),
 last_changed_at timestamptz not null default now(),
 acquisition_status text not null default 'PENDING' check(acquisition_status in ('PENDING','ACQUIRED','FAILED','RESTRICTED')),
 metadata jsonb not null default '{}'::jsonb,
 unique(source_key,source_record_id)
);
create unique index if not exists aero_evidence_content_uniq on public.aero_evidence_objects(content_sha256)
 where content_sha256 is not null;
create table if not exists public.aero_evidence_territory_links(
 evidence_id uuid not null references public.aero_evidence_objects(id) on delete cascade,
 territory_id text not null references public.aero_territories(id),
 parcel_key text not null default '',
 link_type text not null default 'candidate',
 verification_status text not null default 'UNVERIFIED',
 linked_at timestamptz not null default now(),
 primary key(evidence_id,territory_id,parcel_key)
);
create table if not exists public.aero_evidence_fetch_audit(
 id bigint generated always as identity primary key,
 evidence_id uuid references public.aero_evidence_objects(id),
 source_key text not null, source_record_id text not null,
 territory_id text references public.aero_territories(id),
 action text not null check(action in ('FETCH','SKIP_UNCHANGED','SKIP_DUPLICATE','NOT_MODIFIED','FAILED','RESTRICTED','VERIFY')),
 status_code integer, content_sha256 text, etag text, last_modified text,
 occurred_at timestamptz not null default now(),
 details jsonb not null default '{}'::jsonb
);
create index if not exists aero_fetch_audit_ref_idx on public.aero_evidence_fetch_audit(source_key,source_record_id,occurred_at desc);
alter table public.aero_territories enable row level security;
alter table public.aero_evidence_objects enable row level security;
alter table public.aero_evidence_territory_links enable row level security;
alter table public.aero_evidence_fetch_audit enable row level security;
revoke all on public.aero_territories,public.aero_evidence_objects,public.aero_evidence_territory_links,public.aero_evidence_fetch_audit from anon,authenticated;
