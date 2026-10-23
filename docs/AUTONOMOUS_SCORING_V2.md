# Autonomous search and scoring v2

## What was wrong (measured on the Oct 23 data)

| Symptom | Cause |
|---|---|
| 4,430 parcels crawled, 0 eligible, all `RESEARCH_REQUIRED_RESIDENTIAL_CLASSIFICATION` | Crawler read `LAND_USE`/`USE_CODE`/`PROPERTY_TYPE`; every value came back blank, so `single_family_verified` could never be true |
| Imagery verified for 60 parcels only | `collect_mngeo_aerial.py` hard-caps at 60 and reads the original manifest |
| 54 of 60 parcels share priority 60 | v1 priority only sums missing-evidence points |
| 0 condition scores | Needs human-reviewed close-range evidence (kept; this is a correct gate) |

## What changed

1. `collector/residential_classifier.py` discovers the layer's real use-type fields from its own `?f=json`
   metadata (cached in `evidence/data/parcel_schema.json`, refreshed monthly) and classifies from source values.
   `single_family_verified` is true only when the source text says single family. `residential_likelihood`
   is a separate, unverified ranking aid.
2. `scripts/autonomous_residential_crawler.py` uses it, records `use_attrs`, `zip`, `residential_class` and an
   imagery `bbox_4326` (parcel extent, capped for large lots). Verified non-residential parcels are skipped.
3. `scripts/backfill_parcel_attributes.py` drains the 4,430 existing records on the cron, resumable.
4. `collector/aerial_coverage.py` removes the 60 cap. Prioritized (verified single-family first), time-budgeted,
   circuit-breaker, `--both-vintages` for change detection. Ledger stores hash + bytes + layer + bbox, never pixels.
5. `collector/roof_chip_features.py` (experimental): blue-tarp and year-over-year change flags from the
   central crop. Review flags only, low weight.
6. `scripts/roof_score_v2.py`: `priority = 100 * (1 - exp(-1.6 * ev))`, where
   `ev = P(age) x storm x imagery flag x job size x class`. Every factor is written per parcel with flags.
7. `scripts/build_review_queue.py`: `priority x (0.5 + (1 - confidence))` so high-priority, thin-evidence parcels
   go to a reviewer first; CSV is pre-filled with source and image hash and matches `roof_observations.json`.
8. `collector/weak_label_model.py`: calibrates against reroof-permit outcomes, features as of the year before
   the permit. Refuses to train under 150 per class (today there are about 18 matched properties).

## Gates kept

- `roof_condition_score` still comes only from `roof_evidence_score.py` after human-reviewed close-range evidence.
- Aerial-only is never a condition score. Google imagery stays out of any model workflow.
- A missing permit is unknown. Only a verified final reroof permit resets roof age.
- Nothing in v2 says damage. `not_a_damage_score: true`, `condition_claim: "NONE"` on every record.

## Not verified yet (needs network, which was unavailable when this was built)

- The Met Council layer's actual field names. Run `python3 collector/residential_classifier.py` once; it prints
  the chosen `use_fields`. If it prints a warning, the layer has no use-type field and you need a join
  (Eagan city layer `EA_PropertyInformation/MapServer/19`, or a county class-code table).
- Live WMS fetches. The fetch and validation code is the existing approved logic; tests use fakes.
- Constants in `CONST` are priors, not calibrated.

## Next, in value order

1. Run the schema discovery, read the real values, extend token lists in the classifier if needed.
2. Extend the NOAA ZCTA storm index from 593 parcels / 4 ZIPs to every ZIP in the crawl. Until then most
   parcels carry `STORM_DATA_NOT_COVERING_THIS_ZIP`.
3. Add a building-footprint layer so chips are masked to the roof instead of a center crop.
4. Connect the municipal permit exports (Eagan, then outward) to grow real labels for calibration.
5. Reviewers fill `review_queue.csv`; load results into `roof_observations.json`. Every review is also a label.
6. Move ledger and score history out of Git (Supabase) once the repo grows; the cron commits on change.
7. Rights review for MnGeo/Dakota imagery before any automated pixel analysis beyond the experimental flags.
