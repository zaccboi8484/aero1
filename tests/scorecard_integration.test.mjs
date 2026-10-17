import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {assemble} from '../api/roofing-scorecards.js';

const D=new URL('../evidence/data/',import.meta.url);
const file=name=>readFileSync(new URL(name,D),'utf8');
function source(){
 return {
  parcels:file('kingswood_parcel_candidates.csv'),
  permits:JSON.parse(file('municipal_permit_export_audit.json')),
  roofing:JSON.parse(file('roof_evidence_scores.json')),
  valuation:JSON.parse(file('live_property_enrichment.json')),
  imagery:JSON.parse(file('fast_validation_report.json'))
 };
}
test('original residential 60 join keeps all permit matches and honest evidence statuses',()=>{
 const x=assemble(source());
 assert.equal(x.original_60_only,true);
 assert.equal(x.counts.residential_properties,60);
 assert.equal(x.counts.municipal_export_permit_matches,25);
 assert.equal(x.counts.residential_properties_with_permit_matches,18);
 assert.equal(x.counts.valuations_source_matched,56);
 assert.equal(x.counts.research_priority_cards,60);
 assert.equal(x.counts.human_reviewed_roof_scores,0);
 assert.equal(x.counts.evidence_approved_mindex,0);
 assert.equal(x.counts.government_imagery_response_hashes,60);
 assert.equal(new Set(x.records.map(r=>r.county_pin)).size,60);
 assert.equal(x.records.filter(r=>r.roof_permit_candidate).length,1);
 const important=x.records.find(r=>r.address.startsWith('1459 Kings Wood Lane'));
 assert.ok(important);
 assert.equal(important.permit_matches.find(p=>p.permit_number==='2506-00458-BL').issued_date,'2025-06-20');
 assert.equal(important.permit_matches[0].final_roof_replacement_verified,false);
 assert.equal(important.roof_condition_score,null);
 assert.equal(important.mindex_score,null);
});
test('a duplicate municipal permit is rejected before any card is issued',()=>{
 const data=source();
 data.permits.records.push({...data.permits.records[0]});
 assert.throws(()=>assemble(data),/duplicate municipal permit/);
});
test('no auto-approved roof score or fake physical evidence',()=>{
 const data=source();
 const p=data.roofing.records[0];
 p.roof={status:'NOT_SCORED',roof_condition_score:80};
 assert.throws(()=>assemble(data),/Unreviewed physical score blocked/);
});
