-- GateKeeper identity & crawl search catalog. Apply only to a provisioned Supabase DB.
create table if not exists public.aero_property_identity(
 id uuid primary key default gen_random_uuid(),
 county_code text not null check(length(county_code)>0),
 county_pin text not null check(length(county_pin)>0),
 source_object_id text, situs_address text,
 municipality text, jurisdiction text,
 identity_status text not null default 'SOURCE_CANDIDATE'
   check(identity_status in ('SOURCE_CANDIDATE','VERIFIED','SUPERSEDED','DISPUTED')),
 source_url text not null check(source_url ~ '^https://'),
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(county_code,county_pin)
);
create table if not exists public.aero_property_territory(
 property_id uuid not null references public.aero_property_identity(id) on delete cascade,
 territory_id text not null references public.aero_territories(id),
 membership_status text not null default 'CANDIDATE'
   check(membership_status in ('CANDIDATE','VERIFIED','REJECTED')),
 primary key(property_id,territory_id)
);
create table if not exists public.aero_source_registry(
 source_key text primary key,
 official_host text not null,
 jurisdiction text not null,
 category text not null,
 priority integer not null default 10,
 enabled boolean not null default false,
 requires_auth boolean not null default false,
 min_refresh_hours integer not null default 168 check(min_refresh_hours between 1 and 8760),
 terms_review_status text not null default 'PENDING',
 created_at timestamptz not null default now()
);
create table if not exists public.aero_crawl_checkpoint(
 source_key text not null references public.aero_source_registry(source_key),
 source_record_id text not null,
 canonical_url text not null check(canonical_url ~ '^https://'),
 etag text,last_modified text,content_sha256 text,
 last_success_at timestamptz,
 next_eligible_at timestamptz,
 attempts integer not null default 0,
 last_error text,
 primary key(source_key,source_record_id)
);
create index if not exists aero_checkpoint_due_idx on public.aero_crawl_checkpoint(next_eligible_at,last_success_at);
create table if not exists public.aero_permit_identity(
 id uuid primary key default gen_random_uuid(),
 issuing_jurisdiction text not null,
 permit_number text not null,
 normalized_site_address text,
 property_id uuid references public.aero_property_identity(id),
 type_raw text, status_raw text, issue_date date,
 source_url text not null check(source_url ~ '^https://'),
 evidence_id uuid references public.aero_evidence_objects(id),
 review_status text not null default 'UNVERIFIED'
   check(review_status in ('UNVERIFIED','MATCH_CANDIDATE','VERIFIED','REJECTED')),
 unique(issuing_jurisdiction,permit_number)
);
create index if not exists aero_permit_property_idx on public.aero_permit_identity(property_id);
alter table public.aero_property_identity enable row level security;
alter table public.aero_property_territory enable row level security;
alter table public.aero_source_registry enable row level security;
alter table public.aero_crawl_checkpoint enable row level security;
alter table public.aero_permit_identity enable row level security;
revoke all on public.aero_property_identity,public.aero_property_territory,
public.aero_source_registry,public.aero_crawl_checkpoint,public.aero_permit_identity from anon,authenticated;
-- No blanket authenticated read: application must use a scoped server API.
