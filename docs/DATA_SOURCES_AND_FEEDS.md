# Where each input comes from and how to get it

## Parcel-level hail (collector/hail_swath.py)
- **Source:** NOAA MRMS MESH (Maximum Estimated Size of Hail), 24-hour running max. Public bucket `s3://noaa-mrms-pds`,
  key pattern `CONUS/MESH_Max_1440min_00.50/<YYYYMMDD>/MRMS_MESH_Max_1440min_00.50_<YYYYMMDD>-<HHMMSS>.grib2.gz`.
- **Format:** every file is gzip-compressed GRIB2, millimetres, 0.01 degree (~1 km) grid. Decompress, then decode with
  `xarray` + `cfgrib` (needs the ecCodes library: `apt install libeccodes-dev`).
- **Access:** anonymous HTTPS, no account: `https://noaa-mrms-pds.s3.amazonaws.com/?list-type=2&prefix=CONUS/MESH_Max_1440min_00.50/20260501/`.
  Field definitions: NSSL operational MRMS GRIB2 tables.
- **Which days:** days with a NOAA Storm Events HAIL report in scope (file you already ingest). SPC same-day reports
  (`https://www.spc.noaa.gov/climo/reports/YYMMDD_rpts_hail.csv`) can add the newest days before NCEI publishes; confirm
  that URL pattern before relying on it. I could not confirm how far back the bucket's archive reaches: run
  `collector/hail_swath.py` on a 2021 date first, and if keys are missing the run leaves that day unprocessed (so coverage stays false).
- **Caveat:** a radar ESTIMATE at ~1 km. It is a ranking input only.

## Outreach outcomes (scripts/outcome_feedback.py)
- **Source:** your own work. Nobody publishes it. Flow: `export_outreach_list.py` writes the list with tier/priority at
  export time, your CRM/dialer/field app records an outcome per pin, then export a CSV or write rows to the Supabase
  table in `supabase/migrations/008_outreach_outcomes.sql`.
- **Columns:** export_id, county_pin, tier_at_export, priority_at_export, outcome, outcome_at. No names, phones or emails.
- **Use:** `python3 scripts/outcome_feedback.py --csv outcomes.csv` (or `--supabase` with `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`).
  DO_NOT_CONTACT outcomes feed `outreach_suppression.json`, which scoring honors.
- **Needs volume:** monotonic tier check and calibration report only after 100+ attempts per tier.

## Reviewed roof ages (cohorts, reroof timeline)
- Reviewers write `evidence/data/roof_age_reviews.json`: `{"records":[{"county_pin","status":"REPLACED"|"ORIGINAL","year","reviewer_id","reviewed_at"}]}`.
  Entries without reviewer_id and reviewed_at are ignored.

## Imagery vintages for the reroof timeline
- `collector/aerial_coverage.py --both-vintages` fetches met25 (2025) and dak23 (2023). Rights review still applies.
