# Original AeroLeadAI v1.1: verified source-pattern reconciliation

Reviewed file: `AeroLeadAI_and_GateKeeper_Fixed_v1_1-2.zip` (user Library, inspected October 2026). This documentation is a source audit, not a claim of completing an image crawler.

## Reused behavior and exact file locations

- `AeroLeadAI_Standalone_Local_v1_1/app/engine.py`: event-driven scores by independent **storm**, **imagery**, **property** and **permit** evidence; negative-polarity offsets; evidence-source corroboration; distinct confidence; four tier labels. These are heuristic formulas. Never auto-score a property just because a parcel or Street View link exists.
- `GateKeeper_v3_2_Evidence_Polarity_Fix/gatekeeper/adapters/web_research.py`: stdlib urllib research probe returning HTTP status/content type and a success/error envelope. Network errors fail closed; it samples only 4096 bytes and does **not** collect images or search external sites.
- `AeroLeadAI_Render_Standalone_v1_1/app/engine.py`: same scoring semantics as local version.
- `GateKeeper_v3_2_Evidence_Polarity_Fix/gatekeeper/investigation/planner.py`: investigation planning, not real imagery acquisition.

## Explicit absences in original archive

No working Google Street View panorama fetcher, image search/crawler, image rights adapter, image analysis workflow or automatically populated property photographs were found. Do not cite these as original working integrations. Original `engine.py` expects imagery *evidence events*, not direct image source harvesting.

## Contract for Kings Wood property cards

1. Use GIS parcel IDs and coordinates from official source manifests for parcel association; preserve acquisition timestamps and citations.
2. Render **Google Street View as an outbound Maps panorama URL only**, using **numeric GIS lat,lon** for `map_action=pano&viewpoint=lat,lon`. If coordinates are unavailable, show an ordinary Google Maps address search labeled accordingly. Coverage and exact frontage are not guaranteed; GIS parcel center is an approximate target.
3. Do **not** proxy, scrape, store, thumbnail, or assign Google Street View/Google Photos content to AeroLeadAI's evidence image library.
4. Evidence imagery belongs to separately licensed/authorized Dakota County aerial imagery or property-owner-supplied photos, with acquisition date, image identifiers, source URL, hash, and terms. County imagery may not be copied unless permitted by its terms.
5. Permit records require City of Eagan source IDs, exact/reviewed address match, jurisdiction check, and traceability. No-permits-returned is not evidence of no-permits-exist.
6. Mindex remains **Not scored** unless input events and their polarity, provenance, independent corroboration and review status support calculations. Heuristic rank is not an estimate of roof damage probability.

## Implemented, not merely promised

- 60 GIS candidates in `evidence/data/kingswood_parcel_candidates.csv`
- GPS-tagged Dakota County GIS aerial requests in `evidence/data/imagery_manifest.json`
- City permit reconciliation in `collector/match_permits.py`
- User-facing link-only Google Street View using GIS centerpoints in `index.html`
- HTTP-source adapter and scoring guidelines above remain guidance until fully ported to operating coordinator
