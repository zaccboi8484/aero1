# City of Eagan — actual public records retrieval action (22 October 2026)

## Why the unattended municipal search is blocked
GitHub Actions' direct public GET of `https://eagan.onlama.com/Dashboard.aspx` reports HTTP 403. The City's published Open Data dashboard contains previous-month, previous-year, open, and last-90-day permit reports. These subsets are not complete histories, and a successful query returning no rows cannot prove "no roof permit." The City says permits and inspection results are available to suitable authenticated applicants/account holders.

Official routes:
- Public data request portal: https://cityofeaganmn.nextrequest.com/
- Public city permit data: https://eagan.onlama.com/Dashboard.aspx
- City Building Inspections: https://www.eaganmn.gov/buildinginspections
- City permit instructions: https://www.eaganmn.gov/permithandouts
- Data Practices Act: https://www.revisor.mn.gov/statutes/cite/13.03

## What the new pipeline actually generates
- `evidence/data/eagan_municipal_record_request_all_parcels.csv`: every currently indexed Eagan property with actual Metropolitan Council GIS county PIN, address, batch origin and documented permit IDs from the existing City report exports.
- `evidence/data/eagan_municipal_record_request_status.json`: count and proof that the packet has NOT been submitted and no issuer document has been verified.
- Source registry must pass uniqueness and "official GIS discovery complete" checks. No invented permits, no implied roof work completion.

## Prepared request — paste into the official NextRequest form

Subject: Minnesota Chapter 13 public data request — existing building/roof permit index and inspection history for Eagan GIS parcel list

I request to inspect and receive copies of existing PUBLIC government data, pursuant to Minnesota Statutes Chapter 13. For each property in the attached `eagan_municipal_record_request_all_parcels.csv` (actual official GIS county parcel PINs and Eagan situs addresses), please provide any existing issuer-maintained building permits, reroof permits, roof replacement/repair scope descriptions, applications, issue dates, status history, final inspection results and documented closure dates.

The first 60 rows are the priority research batch. We also provide actual City-report permit numbers for 25 previously matched records affecting 18 of these properties. Please prioritize those exact permit IDs, particularly `2506-00458-BL` associated with 1459 Kings Wood Lane. For the additional Eagan properties, we seek an existing public searchable permit/address index or maintained electronic export first; we will agree to reasonable staging if retrieving all underlying records at once is burdensome.

Please identify the years covered by any database or report and explain if older archived records are held elsewhere. To avoid false conclusions, we need both permit matches and the **coverage limits of the index**. Please provide existing data in the electronic format maintained, if available; the request does not require you to invent new reports, perform inspections, or certify any roof's condition.

If a portion contains restricted data, please identify the classification and provide non-exempt public portions. We ask for notice of applicable copying costs before work incurring a charge.

## GateKeeper handling rules
- A City report match is not a City original issuer document, and a permit issuance is not a final inspection.
- A City portal 403 must NEVER trigger credential bypass, CAPTCHAs, rotating proxies or disguised scraping.
- Do not publish restricted personal data or private requester details in public GitHub or unauthenticated UI.
- Do not mark any of the city permit histories complete until the issuer supplies coverage dates and reviewable source records.
- The request is PREPARED ONLY. The user or authorized representative must submit it, since the form requires a contact email and an accountability decision. We have NOT filed anything on the user's behalf.

## Next improvement after City responds
An authorized backfill importer should match issuer record ID and exact parcel PIN/address, retain source report hash and permitted date range, store original files in restricted storage, and require independent review before changing `last_permit_status` or labeling any roof replacement complete.
