# AeroLeadAI GateKeeper — source imagery and redistribution gate

Date: 2026-10-19

## Verified sources, not invented roof imagery

Original Kings Wood 60 parcels have prior official Minnesota Geo WMS JPEG responses in `evidence/data/fast_validation_report.json`, including exact SHA-256 hashes and approved remote source URLs. `collector/validate_imagery_view_sources.py` publishes a separate original-60 register of those real *remote-source observations*. This is not an image download, local image file, roof-condition score, Mindex score or a guarantee a provider remains online.

The source-image layer actually used by the original 60 is the State of Minnesota/MnGeo `https://imageserver.gisdata.mn.gov/cgi-bin/wmsll?` WMS, including Metropolitan Council `met25` (2025 metro aerial) with possible `dak23` (2023 Dakota imagery) fallback. Provider documentation:
- https://mn.gov/mngeo/gis-data-and-maps/web-map-services/mngeo-image-service/technical.jsp
- https://mn.gov/mngeo/gis-data-and-maps/web-map-services/mngeo-image-service/data.jsp

## Why automatic county imagery mirroring was disabled

The former `.github/workflows/download-images.yml` attempted to commit 2025 Dakota County 6-inch aerial JPEGs directly to the repository. Its Oct 19 run reported all 60 FAILED because the cache decision returned `SKIP_RECENT` without any locally persisted JPEG bytes. A cache-hit metadata record cannot be presented as a successful image download.

More importantly, metadata for the 2025 high-resolution Dakota County ImageServer attributes copyrighted imagery to Nearmap US Inc. and includes commercial-use/redistribution restrictions; a commercial roofing-lead app must not assume public GitHub redistribution permission.
Source metadata:
https://www.arcgis.com/sharing/rest/content/items/273decab74d04e6998b7db3142980767/info/metadata/metadata.xml?format=default&output=html

Until redistribution rights are actually confirmed, the scheduled workflow verifies and links *remote WMS sources* without copying the pixels into GitHub. The old manual downloader was preserved for provenance but should not be run to mirror county/Nearmap images without rights review. The historical `imagery_downloads.json` with `downloaded:0` remains truthful.

## GateKeeper release labels

- `REMOTE_GOVERNMENT_JPEG_LAST_VERIFIED`: genuine prior response bytes plus SHA-256 and source URL, not an inspection or present-time network guarantee.
- `SOURCE_NOT_VALIDATED`: unavailable or insufficient source check, not a damaged roof.
- `locally_downloaded:false` and `resale_or_redistribution_rights_verified:false`: always explicit.
- The working live viewer uses real source links as provided by MnGeo; an orbit effect remains a 2D view animation, not photogrammetric 3D.

The scheduled source audit can complete autonomously. Manual review is still required for image rights, physical property condition and original municipal permit documents.
