# AeroLeadAI v1.4 — non-destructive integration review (2026-10-18)

## Scope and the source of truth
- The user-provided `AeroLeadAI_Latest_v1.4.zip` was inspected and archive integrity checked; bundled offline tests passed (11 Python, 6 Node).
- GitHub `zaccboi8484/aero1` `main` remains authoritative for the existing residential platform, 60 Kings Wood properties, existing 25 permit-export matches, 56 source-matched valuations and GateKeeper release rules.
- Production: `https://aeroleadaigithubreadyv03.vercel.app`, successfully checked by real HTTP smoke tests (see `tests/production_http_smoke.mjs`). No claim that any unreviewed roof is damaged or physically inspected.

## Safe additive improvements
1. `collector/groq_extract.py`: opt-in, manually invoked, capped at 20 short records per run, explicit `--send-to-groq`, server-only `GROQ_API_KEY` and explicitly selected `GROQ_MODEL`. Every extraction is a **UNVERIFIED_PROPOSAL**; no published property damage score or municipal verification occurs. No model request in CI or scheduled jobs.
2. `security/apiGuard.mjs`: optional, standalone bearer/origin gate for future sensitive API routes; not connected to or replacing existing cookie-based `api/auth.js`.
3. Add regression tests for the two modules, alongside original-60/25-permit source joins, duplicate rejection, and GateKeeper invariants.

## Deliberately excluded from merge
- Do not replace `collector/gatekeeper_pulse.py`, `validate_mn_addresses.py`, `collect_mngeo_aerial.py`, their CI schedules, or current UI with the older standalone ZIP copies. Those would downgrade or conflict with functioning source collectors and present inaccurate versions of evidence.
- Do not copy the ZIP's archived Next.js starter or `public/index.html` over the existing production app. The live property cards and authenticated API remain as deployed.
- Do not apply `supabase/migrations/20261018_aeroleadai_v1_v9_pipeline.sql`: it assumes existing `public.properties`, creates `contractors`/`lead_claims` for a marketplace **outside the residential property intelligence scope**, and contains potentially destructive cascade semantics. The ZIP claims it was applied to a named project, but the connected Supabase account currently lists no accessible projects; provenance of that database is unverified.
- Do not import bundled `evidence/data` snapshots to production: existing GitHub data have newer actual crawling and permit evidence. Do not overwrite or duplicate property records.
- Do not copy bundled local approval logs as an immutable audit: local hashes alone do not prevent privileged rewriting.

## GateKeeper requirements still outstanding
- Supabase append-only decision audit (no connected database verified).
- Authenticated source-level municipal permit document and inspection review.
- Human image interpretation and condition scoring (currently no reviewed scores).
- Zero fabricated Mindex scores; source availability and image hashes are not property defects.
- Property selection is residential only. Optional external model use requires actual human authorization and review of what text may be shared with that provider.
- Existing production HTTP checks must remain green after every deployment.

**Upgrade principle:** No replacement of working files or original data, no automated paid/external API calls, and no version-completion claims without an auditable test result.
