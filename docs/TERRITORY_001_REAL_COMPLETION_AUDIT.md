# Territory 001 — verified delivery reconciliation (2026-10-16)

This is the source-of-truth progress note for AeroLeadAI/GateKeeper. Never confuse source discovery with property completion.

## User-requested definition of a completed property
A completed property has (1) a verified parcel and subdivision assignment, (2) permit search attempted with outcome, date, and source and source-record links if found, (3) authorized imagery or explicit documented no-image result, (4) evidence-classification decision and provenance, (5) property value with assessment date/source or honest unavailable status, (6) Mindex score only if eligible evidence reviewed; otherwise NOT_SCORED, (7) GateKeeper audit record. Completion is PER-PROPERTY, not one aggregate 60-row CSV.

## Actual collected evidence, not samples
- 60 GIS parcel candidate rows in evidence/data/kingswood_parcel_candidates.csv. County PIN, address and plat labels originate from official ArcGIS query. Plat/spatial membership not individually certified.
- Three actual city GIS subdivision records in evidence/data/official_source_discovery.json: Kings Wood 2nd, 4th, 5th Addition (city subdivisions layer 9).
- City of Eagan permit open-data dashboard exists (https://eagan.onlama.com/Dashboard.aspx). Collector's attempt returned HTTP 403. No property-specific permit export or match file exists in this repository. 0 verified matches is a statement about OUR inventory, not the homes' permit histories.
- 60 county aerial JPEG downloads attempted in evidence/data/imagery_downloads.json: downloaded 0, failed 60 (invalid JPEG bytes). Indexed imagery URL/coordinates do not count as downloaded imagery.
- Mindex scores: 0 evidence-supported published scores. GateKeeper reviewed findings: 0.
- Supabase persistence: no connected project visible in available Supabase connector.
- LuckyG: in-browser local-first memory and answer rules, not an autonomous internet agent; no paid AI required.
- Vercel: static dashboard deployed independently of original scanner; backend ingestion unconfirmed.

## Ring expansion acceptance gate
Do not declare Territory 001 complete or automatically promote Burnsville/ring candidates into a validated neighborhood until every targeted property has an audit row explaining permits, imagery, evidence and scoring outcomes. May collect subsequent ring leads as unverified while seed work continues, but label those leads clearly and retain ring number, anchor geometry and provenance.

## Critical next engineering tasks
1. Obtain city-supported 200-row CSV exports/search results or authorized access for each Eagan address; preserve the raw original and hash. See https://eagan.onlama.com/Help.aspx. Do not evade HTTP 403 or use credentials from unrelated projects.
2. Run collector/match_permits.py on original exports, audit matching and outstanding searches.
3. Diagnose ImageServer export responses/permissions and terms; do not mislabel HTML/errors as JPEG evidence.
4. Pull GIS polygon geometries and confirm each parcel intersects the three recorded plat polygons, including parcel splits or exclusions.
5. Load verified source records, statuses, and evidence artifacts into an authorized DB, then score reviewed evidence using pipeline/source_adapter.mjs.
6. Update the dashboard's public counters from real audit rows; implement rings only with geospatial boundary and ordering.
