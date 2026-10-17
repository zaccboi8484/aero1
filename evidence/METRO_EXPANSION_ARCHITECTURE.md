# Seven-county regional expansion architecture

The downloadable **AeroLeadAI_Metro_Expansion_v1.zip** contains a Python municipal-boundary ring collector, a Supabase property identity schema, source registry and operational runbook. Saved to ChatGPT Library.

## Canonical identity
- `county + county_pin` is the current identity namespace; retain historical PIN aliases to track splits/mergers.
- Permit record uniqueness is `issuing jurisdiction + original permit number`; ambiguous address matches remain `UNVERIFIED`.
- The same evidence object can be linked to Kings Wood, Burnsville or a future metro territory without duplication.
- Fetch ledger uses `source + original record ID`, response ETag/Last-Modified, and SHA-256 byte content; avoid unnecessary re-downloads.

## Chain of command
1. MetroGIS parcel polygon and municipality authority
2. Municipality source adapter (Eagan or Burnsville)
3. Per-source queue and rate limiter
4. Conditional HTTP fetch / byte hash deduplication
5. GateKeeper validation and review
6. Append-only fetch audit and access-controlled original storage
7. Supabase Postgres canonical identity and read API
8. Vercel dashboard, reporting only reviewed evidence

## Ring ordering
10 / 20 / 35 / 55 / 80 km from Kings Wood as discovery order, always clipped to real seven-county municipality boundaries. Source: https://arcgis.metc.state.mn.us/arcgis/rest/services/LPH/Administrative_Library/FeatureServer/3

Seven counties: Anoka, Carver, Dakota, Hennepin, Ramsey, Scott and Washington.

## Source registry
- Shared official parcel polygons: https://arcgis.metc.state.mn.us/arcgis/rest/services/LPH/Administrative_Parcels/FeatureServer/0
- Official Burnsville permit history: https://www.burnsvillemn.gov/2042/Permits-Licenses
- Official Eagan permit reports: https://eagan.onlama.com/Dashboard.aspx
- Metro image data: https://mn.gov/mngeo/gis-data-and-maps/web-map-services/mngeo-image-service/data.jsp

Supabase currently has no accessible project through the connected account; schema in the ZIP is **not applied**. A deployed Vercel static viewer is not equivalent to a connected property database.
