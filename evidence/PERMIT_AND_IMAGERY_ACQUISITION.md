# Eagan permits and source-backed imagery: acquisition notes

Collected GIS snapshot: [60 parcel candidates](data/kingswood_parcel_candidates.csv), with [provenance manifest](data/collection_manifest.json). These are **unverified plat/street candidates**, NOT 60 completed property investigations.

## Authoritative sources

1. [City of Eagan public permit reports](https://eagan.onlama.com/Dashboard.aspx): downloadable monthly, previous-year, open, HVAC, plumbing, and recent building permit reports. Exported CSV files must be preserved verbatim in an access-controlled evidence store before address normalization and parcel join.
2. [City of Eagan public search](https://eagan.onlama.com/Search.aspx): query individual street addresses to reconcile historic permits. Public search exports up to 200 records; advanced searches require login. [Official instructions](https://eagan.onlama.com/Help.aspx).
3. [City of Eagan official subdivisions and parcels ArcGIS](https://gis.cityofeagan.com/arcgis/rest/services/EA_PropertyInformation/MapServer): Subdivisions layer 9; parcels layer 19. Use these to verify subdivision membership spatially. No speculative street name = subdivision assumption.
4. [Dakota County official oblique/aerial viewer](https://gis.co.dakota.mn.us/ObliqueViewer/): review acquisition dates and image rights before saving original image or deriving roof/tree assertions.
5. [Dakota County subdivision plat search](https://dakotacountymn.gov/residents/home-property/plat-surveys/online-search): obtain and attach true recorded plat documents.

## Evidence join

A record is matched only when (a) authoritative parcel identifier is present and source verified, (b) city permit address normalized and matched with review, (c) original permit number/type/status/date and source URL are retained. No inference about roof damage from issuance of a roofing permit. No permit search results does not mean no permits exist.

## Current facts

- 60 authentic candidate records currently in GitHub import (not certified Kings Wood boundary)
- 0 permit packets/records verified against those candidates
- 0 usable photographic evidence files attached
- 0 verified condition findings
- Supabase account lists no projects accessible through connector; service-role keys must never be uploaded to public GitHub
- Automated GitHub Actions parcel crawler code runs on push and scheduled Mondays, without a personal API key.
