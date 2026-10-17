# AeroLeadAI residential scorecard integration gate

The source of truth remains the original 60 county parcels. The owner-provided Eagan permit CSV matching audit contains 25 deduplicated permit events on 18 properties; these are source-report matches, not independently inspected municipal permits.

Do not publish damage/Mindex scores without human-reviewed physical-condition evidence. A priority number in roof_evidence_scores.json is ONLY a research-order metric. Permit absences mean unknown. The source-response hash for an aerial image is not a condition inspection.

Outstanding: restore the index dashboard's permit counter and roof-priority reader, confirm deployed Vercel source, complete human permit and imagery review, and connect authorized Supabase append-only audit storage. Nothing in this note certifies 10/10 operational readiness.
