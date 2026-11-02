-- 009: durable crawl completion / retry state; complements 004 queue.
-- Server-side service_role only. Never expose the service key in a browser.
create table if not exists public.aero_crawl_run_events (
 id bigint generated always as identity primary key,
 job_id uuid not null references public.aero_crawl_jobs(id) on delete cascade,
 worker_id text not null,
 event_type text not null check (event_type in ('COMPLETED','RETRY','FAILED')),
 error_message text,
 occurred_at timestamptz not null default now()
);
create index if not exists aero_crawl_run_events_job_time on public.aero_crawl_run_events(job_id,occurred_at desc);
alter table public.aero_crawl_run_events enable row level security;
revoke all on public.aero_crawl_run_events from anon,authenticated;

-- Only the worker holding a live lease may resolve the job. A late worker cannot overwrite another worker's claim.
create or replace function public.aero_finish_job(p_job_id uuid,p_worker text,p_success boolean,p_error text default null)
returns boolean language plpgsql security invoker set search_path=public as $$
declare j public.aero_crawl_jobs%rowtype; kind text;
begin
 select * into j from public.aero_crawl_jobs
 where id=p_job_id for update;
 if not found or j.status<>'processing' or j.worker_id is distinct from p_worker
    or j.lease_until is null or j.lease_until<=now() then
  return false;
 end if;
 if p_success then
  update public.aero_crawl_jobs set status='completed',lease_until=null,worker_id=null,last_error=null,updated_at=now() where id=p_job_id;
  kind:='COMPLETED';
 elsif j.attempts>=j.max_attempts then
  update public.aero_crawl_jobs set status='failed',lease_until=null,worker_id=null,last_error=left(coalesce(p_error,'unspecified failure'),1000),updated_at=now() where id=p_job_id;
  kind:='FAILED';
 else
  update public.aero_crawl_jobs set status='queued',lease_until=null,worker_id=null,
   available_at=now()+make_interval(secs=>least(3600,30*power(2,least(j.attempts-1,7))::int)),
   last_error=left(coalesce(p_error,'unspecified failure'),1000),updated_at=now() where id=p_job_id;
  kind:='RETRY';
 end if;
 insert into public.aero_crawl_run_events(job_id,worker_id,event_type,error_message)
 values(p_job_id,p_worker,kind,case when p_success then null else left(coalesce(p_error,'unspecified failure'),1000) end);
 return true;
end $$;
revoke all on function public.aero_finish_job(uuid,text,boolean,text) from public,anon,authenticated;
grant execute on function public.aero_finish_job(uuid,text,boolean,text) to service_role;
