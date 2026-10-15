# Independent crawler pipeline

Source discovery and adjudication are independent from the UI.

1. **Crawler** fetches only configured, allowed sources and emits raw observations to a queue.
2. **Queue** is the lightweight Postgres table `aero_crawl_jobs`, with atomic leases and retry budget.
3. **Coordinator** validates schema, source identity, territory, evidence, and dedupe key before writing `aero_crawl_audit`.
4. **Supabase audit** stores *post-processed* outcomes, never a guessed roof/driveway/tree condition.
5. **UI** reads reviewed findings separately. Illustrative camera zoom/flydowns are not inspection evidence.

Configuration: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `CRAWLER_SOURCE_URL`, `CRAWLER_WORKER_TOKEN`.

No external crawler target is configured by default. Do not crawl a service without checking its terms, access method, and request limits.
Never expose service-role credentials to the browser. Apply the SQL migration before starting the worker.
