# Core Architect ZIP adapter and search-engine extraction

Source (user-provided): `AeroLeadAI-Core-Architect-PreStudio-10of10-Hardened (2).zip`.

## Relevant modules

- `app/.../engine/IntelligenceProviders.kt`: `PropertyEnrichmentProvider.enrich(property)` and `IntelligenceProvider.analyze(property, signals, history)` are **interfaces**, not working web/search engines.
- `app/.../engine/OpportunityEngine.kt`: deterministic weighted score, separate confidence, reasons, stable decisions. `LocalSignalProvider` returns two explicit placeholder signals: storm exposure = 50, property value = 60, and a target-profile example = 75. These are **not legitimate source evidence**; do not ingest into production.
- `app/.../engine/DecisionPolicy.kt`: monitor below 60, qualify at 60–79, prioritize at 80+, but only appropriate for validated opportunity scoring.
- `app/.../importer/CsvImporter.kt`: header-aware CSV ingestion; useful for official municipal permit exports.
- `app/.../worker/OpportunityWorker.kt`: WorkManager scheduling, Android-specific; GitHub Actions / backend runner is the appropriate server equivalent.
- `app/.../data/Repository.kt`: transactional writes / persisted audit concepts useful in the future connected DB.

## What the ZIP does NOT provide
No executable Google search engine adapter, Google Street View imagery downloader, Bing search integration, municipal permit API adapter, county ArcGIS collector, or production credentials were identified.

## Safe integration
`pipeline/source_adapter.mjs` ports the original provider boundary to server-side JavaScript, requiring HTTPS provenance, source record ID, parcel ID, timestamp, data type, normalized value and confidence. It fails closed per record; valid records can still pass when another adapter fails. Scoring returns NOT_SCORED absent reviewed and provenance-backed inputs; it does not promote generic parcel/permit links into inspection results.

Actual discovery remains source-specific: county ArcGIS collector; official Eagan permit report export + `collector/match_permits.py`; separate permitted county aerial imagery. Google Street View stays outbound link only. No API keys or sensitive information are committed.
