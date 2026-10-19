# AeroLeadAI / GateKeeper — official source research and certification closure plan

Date researched: 2026-10-19. Applies to **the original 60 Kings Wood Eagan parcels** only. The rest of the 417-parcel candidate index remains candidate research, not 417 certified homes.

## Executive truth

- Official parcel identity 60/60; GIS address points 56/60; sourced GIS valuations 56/60, with assessment-year provenance not published by the queried layer.
- The owner-provided Eagan municipal reports contain 11,700 rows, deduplicated into 25 candidate permit matches at 18/60 original homes. **Zero original issuer permit documents have been independently reviewed.** The single explicit 2025 roofing candidate is 1459 Kings Wood Lane, permit **2506-00458-BL** dated 2025-06-20 in the source export. An independent public index is not municipal final inspection evidence.
- The scheduled GitHub crawler's direct request to Eagan's permitting portal returns HTTP 403. Search must never evade this.
- 60/60 genuine official MnGeo WMS JPEG response hashes are in the source ledger; zero automatically verified roof conditions, zero licensed redistributed photos and zero Mindex.
- Current Vercel production has an authenticated scorecard endpoint, source-refresh UI, government imagery viewer, and existing scheduled crawlers. **Vercel Git automatic deployment remains unlinked**, so code is deployed explicitly; data JSON is read from GitHub dynamically.
- Supabase has *no provisioned project* in the connected account. Migrations 004-006 are only source files; never claim that durable Supabase review storage is running.

## Primary discoveries and safe access routes

| Source | Proven capability | GateKeeper allowed next action | Not allowed to claim |
|---|---|---|---|
| Eagan Open Data | Monthly, previous year, open permits, 90-day building reports | Retrieve public CSV reports manually/with authorized API only | Complete all-time site reroof history from recent reports |
| Eagan permit search | Address / permit number search; CSV export **up to 200 results per search** | Human/authorized account or public browser uses official site, page size <=200; preserve exact issuer response | Anonymous scripted access after HTTP 403, undisclosed private API |
| Eagan original permit details | City approval, document downloads and inspections visible with suitable account/access | Request original City documents, scope, inspections, approval/closure details | Approved/issued permit equals finalized reroof |
| Minn. Stat. §13.03 + State DPO | Public-government-data inspection/copies subject to data classification and response processes | Make targeted public data request to City responsible authority; ask for existing electronic records as maintained | Guaranteed instantaneous bulk CSV or unconditional access to private documents |
| City of Eagan building inspections | A project is not complete until approved final inspection | Require final city inspection status and date for claim of completed permitted reroof | Permit count means project completed |
| City GIS parcel service | Parcel PIN, building/land/total values; layer omits effective assessment year | Request assessor-year provenance, rerun exact PIN joins for 4 missing | 56 values are current tax-year assessed values without evidence |
| MN GIS Address Points | 56/60 exact GIS point matches | Investigate remaining 4 GIS mismatches; USPS OAuth separate | State GIS 'mailable' == USPS certified delivery |
| MnGeo WMS met25 | Real 2025 1-foot metro aerial layers over original 60 | View original source with attribution; checksum and capture/date/rights ledger | WMS imagery by itself certifies physical roof damage; blanket photo redistribution |
| Regional residential permit layer | Regional permit candidate evidence; none in current scoped match | Continue bounded official ArcGIS queries with `exceededTransferLimit` safeguards | Dataset is the full Eagan roof-permit registry |

**Authoritative pages:**
- https://www.eaganmn.gov/buildinginspections
- https://www.eaganmn.gov/permithandouts
- https://eagan.onlama.com/Help.aspx
- https://eagan.onlama.com/Dashboard.aspx
- https://www.revisor.mn.gov/statutes/cite/13.03
- https://mn.gov/admin/data-practices/data/requests/
- https://mn.gov/mngeo/gis-data-and-maps/web-map-services/mngeo-image-service/technical.jsp
- https://mn.gov/mngeo/gis-data-and-maps/web-map-services/composite-image-service/
- https://vercel.com/docs/git/vercel-for-github
- https://supabase.com/docs/guides/database/postgres/row-level-security

## Actual pipeline / task priority

1. **Issuer-document reconciliation first:** exact 25 city report permit IDs, each joined to existing original property ID and county PIN; the explicit 2025 reroof candidate is priority 1. Request original issuer scope, issue date, inspection events and final result. Preserve submitted report row/hash and any corrections; do not infer from generic work descriptions.
2. **Full municipal history coverage:** queue all 60 residences even where no import match exists. Seek time range covered, data source freshness, issuer search method, exact normalized site address and evidence of complete coverage. No-match from partial exports remains UNKNOWN.
3. **Address / valuation matching:** the 4 unresolved GIS addresses and 4 valuation nonmatches are independently actionable to the existing public ArcGIS collectors. Published valuations missing an assessment year trigger separate assessor source verification for all 60.
4. **Image-use/condition separation:** maintain source SHA per WMS response and real source layer/year. Copyright and commercialization of each underlying image layer require source-specific review. Dated roof inspection/authorized high-resolution imagery and named human reviewer are prerequisites to condition scoring.
5. **Scoring release:** do not create Mindex merely because a roof is old, had a permit, or had a valid image response. Release requires evidence IDs and original source, review time, contradictions, score version, and approval recorded in a server-only audit ledger.
6. **Distributed reliability:** serialized/effectively conflict-safe GitHub evidence pushes; bounded official source crawl budgets; idempotent county PIN/permit ID joins; record a clear HTTP 403 and use formal public-data route, not access evasion. Search index re-runs daily and publishes an authenticated API + dashboard.

## Output contracts in this release

- `collector/certification_gap_pipeline.py`: validates real source files, hard-stops on contradictions, produces reproducible task identities and source routing.
- `evidence/data/certification_gap_queue.json`: per-parcel actionable official source links, requirements, priorities, and UNKNOWN/BLOCKED status.
- `evidence/data/certification_gap_summary.json`: true source counts and release blockers.
- `evidence/data/permit_issuer_review_queue.csv`: 25 real source-export issuer permit requests, review pending.
- `api/certification-gaps.js`: session-authenticated, read-only, integrity-gated research API.
- `certification-gaps.html`: accessible glass-style search page integrated into existing dashboard.
- `.github/workflows/gatekeeper-certification-search.yml`: daily re-index with source-linked tests and GitHub's safe push mechanism.

No external service credentials, private permits, user PII or photograph binaries are added to the repository.

## Required next infrastructure decisions

1. **Eagan:** submit the prepared formal data request and/or obtain authorized access to original permit and inspection outcomes. This involves the issuer; no external access can be invented from code.
2. **Supabase:** provision in the user's chosen organization, apply existing schema migrations 004-006 and a reviewed receipt migration, then connect *server-only* service credentials and write append-only review events. The connected organization currently has no DB project; never describe the prepared SQL as applied.
3. **Vercel:** attach existing project to `zaccboi8484/aero1` in Project Settings > Git, enabling code deployments on merges; avoid triggering full production builds for every GitHub Action data-only commit where possible. Existing app remains deployed on the original domain.
4. **Reviewers:** name and verify qualified human reviewers, define a score rubric, author a per-property license/issuer evidence sign-off process, and preserve disagreements/contradictions. A model can extract **candidate** fields, not certify completion.
