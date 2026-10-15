-- Isolated discovery queue and post-coordination audit history.
create extension if not exists pgcrypto;
create table if not exists public.aero_crawl_jobs (
  id uuid primary key default gen_random_uuid(),
  territory text not null,
  source_key text not null,
  dedupe_key text not null unique,
  request jsonb not null default '{}'::jsonb,
  status text not null default 'queued' check(status in ('queued','processing','completed','failed')),
  attempts int not null default 0,
  max_attempts int not null default 4,
  available_at timestamptz not null default now(),
  lease_until timestamptz,
  worker_id text,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists aero_crawl_jobs_poll_idx on public.aero_crawl_jobs(status,available_at);
create table if not exists public.aero_crawl_audit (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null unique references public.aero_crawl_jobs(id),
  territory text not null,
  source_key text not null,
  source_url text,
  source_record_id text,
  verification_status text not null check (verification_status in ('SUPPORTED','UNVERIFIED','CONTRADICTED','INCONCLUSIVE')),
  classification text not null check (classification in ('REAL-NOW','BUILDABLE-NOW','INFRASTRUCTURE-GAP','SIMULATED','FUTURE-INFRASTRUCTURE','UNKNOWN')),
  findings jsonb not null default '{}'::jsonb,
  processed_at timestamptz not null default now()
);
alter table public.aero_crawl_jobs enable row level security;
alter table public.aero_crawl_audit enable row level security;
revoke all on public.aero_crawl_jobs from anon, authenticated;
revoke all on public.aero_crawl_audit from anon, authenticated;
-- Atomic single-job claim; do not expose to browser clients.
create or replace function public.aero_claim_job(p_worker text, p_lease_seconds int default 120)
returns setof public.aero_crawl_jobs language plpgsql security invoker set search_path=public as $$
begin
  return query
  with candidate as (
    select j.id from public.aero_crawl_jobs j
    where ((j.status='queued' and j.available_at<=now()) or
           (j.status='processing' and j.lease_until<now()))
      and j.attempts<j.max_attempts
    order by j.available_at, j.created_at
    for update skip locked limit 1
  )
  update public.aero_crawl_jobs j
  set status='processing',attempts=j.attempts+1,worker_id=p_worker,
      lease_until=now()+make_interval(secs=>greatest(30,least(600,p_lease_seconds))),
      updated_at=now()
  from candidate c where j.id=c.id returning j.*;
end $$;
revoke all on function public.aero_claim_job(text,int) from public,anon,authenticated;
grant execute on function public.aero_claim_job(text,int) to service_role;
