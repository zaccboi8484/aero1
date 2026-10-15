# Evidence engine — real data only

This is runnable, public-source ingestion code for Kings Wood, Eagan. No mock address, simulated damage, or invented permits are promoted.

## What runs now
- `collector/collect_parcels.py` queries Metropolitan Council's Dakota County parcel ArcGIS service and writes `evidence/data/kingswood_parcel_candidates.csv` with source URLs. GitHub Actions runs it on code changes and weekly.
- `collector/match_permits.py` joins an **authentic** City of Eagan permit CSV export to those GIS candidates. It preserves source checksum, permit number, date, type and status, and marks exact-address matches for human review; ambiguous/missing matches stay unverified.
- `pipeline/coordinator.mjs` validates provenance before recording an audit result. A live Supabase project and credentials are necessary for its DB operations.
- `tests/test_permit_matching.py` tests address normalization and fail-closed evidence handling. Its sample input is test-only and is not an evidence dataset.

## Commands
```bash
git clone https://github.com/zaccboi8484/aero1.git
cd aero1
python3 collector/collect_parcels.py
python3 tests/test_permit_matching.py
python3 collector/match_permits.py --permits /secure-downloads/eagan-actual-permit-report.csv
```

## City public permit portal
- https://eagan.onlama.com/Search.aspx
- https://eagan.onlama.com/Dashboard.aspx

Export real municipal permit CSVs. This project does not guess undocumented permit endpoints, bypass logins, or upload sensitive permit packets to a public repository. Store raw documents and reviewer artifacts in an access-controlled bucket once the database is provisioned.

## Verification constraints
1. An exact address match is only a **potential** connection and stays UNVERIFIED until reviewed.
2. Missing permits in a search do **not** certify a clean record.
3. An issued roofing permit does not establish roof damage.
4. Evidence originals and timestamps must be preserved, including acquisition license for county imagery.
5. Crawler outputs are sources, not property condition scores.

## Needed operational dependencies
The Supabase connection currently returns zero projects, so there is no target database for inserting audit rows. Server-side credentials stay off GitHub and the public UI. GitHub Actions parcel snapshots and static Vercel dashboard do not require a service-role key.
