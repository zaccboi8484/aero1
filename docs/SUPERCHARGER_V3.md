# Aero1 Supercharger integration and upgrade #1

This update merges the supplied v2 extension into the current repository while retaining Mindex cards, exports, evidence validation, and existing frontend pages.

## Upgrade #1: building footprints

Implemented in `collector/footprints.py`: load a local Microsoft/Overture-compatible polygon dataset through GeoPandas, transform to EPSG:26915, and find the nearest building within 40 metres. This projection and coordinate guard are Minnesota-specific. Subset large national datasets before use. Source data is not bundled or downloaded automatically.

Matches remain **review required**. Equal-distance matches, overlapping candidates, shared buildings across parcel records, missing coordinates, and invalid geometry do not produce a usable roof-size estimate. Proximity does not establish parcel ownership or identify the main house rather than an outbuilding.

Area uses footprint area × 1.12, an approximate 6/12 roof-pitch assumption, not measured pitch, roof complexity, overhangs, or a roofing quote. Scoring uses `clamp(0.8 + (estimated_area - 200) / 600, 0.8, 1.3)` when a usable footprint exists; otherwise the existing valuation factor remains. Compactness is recorded only as a geometric proxy. It does not independently change priority or confidence.

```bash
python3 -m pip install geopandas rasterio numpy pillow scipy xarray cfgrib eccodes
python3 collector/footprints.py --footprints /path/to/mn-buildings.geojson --source "Dataset provider, release date and license reference"
python3 collector/roof_chip_features.py --chip-dir /path/to/chips
python3 collector/reroof_timeline.py --chip-dir /path/to/chips
python3 scripts/roof_score_v2.py
python3 scripts/build_mindex_cards.py
python3 scripts/export_mindex_leads.py
```

The footprint command writes `evidence/data/building_footprints.json`, including source description, file hash, candidate geometry and area assumptions. Chip analysis automatically uses those geometries with the corresponding aerial-ledger bounds. Tarp, texture and change statistics use only masked pixels. Holes are respected. Empty/tiny masks are rejected; absent matches retain an explicitly labeled center-crop proxy. Existing chips must share the same bounds/orientation across vintages; no automatic image registration is claimed.

No real footprint dataset was supplied in this task. Geometry, masking and scoring were tested with synthetic fixtures; real property matches are not yet verified. Existing imagery use restrictions still apply.

## Other changes

- Added supplied hail-cell exposure, imagery-change timeline, cohort adjustment, uncertainty intervals, review alerts, outcome feedback, drift guard and provenance modules.
- Preserved current Mindex construction, export, and count/claim checks in the discovery workflow.
- Failed imagery probes retry on subsequent runs; timestamps without timezones cannot establish freshness.
- Invalid calendar dates are ignored by event scoring.
- Damaged suppression files stop scoring and exports. Opt-outs persist across feedback imports, and Mindex checks the latest suppression file even with stale cards.
- Atomic JSON replacement protects score and suppression writes from partial-file failures (single-writer assumption).
- Outreach export IDs include seconds and a random suffix; negative export limits are rejected.
- Added offline preflight checks, regression tests and a correctly ordered JavaScript/build test command.
- Included the supplied migration `008_outreach_outcomes.sql`; it has not been applied to a live database.

## Verification commands

```bash
python3 scripts/preflight.py
python3 -m unittest discover -s tests
npm ci
npm test
```

`npm test` runs unit tests, builds React, then verifies final build artifacts. Some unit tests generate static files, so the artifact check must follow the production build.

Preflight passing means local files, packages and JSON are present; it does not certify live services. Ranking constants remain uncalibrated priors. Hail ingestion is candidate-report-day coverage, not comprehensive radar coverage. No output is a roof damage or insurance finding. Live MRMS feeds, large-grid runtime, database migration and actual footprint matching require deployment validation.
