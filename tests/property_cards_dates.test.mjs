import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {calendarDate,permitCardFacts,stormCardFacts,roofReviewNeeds} from '../api/property-card-intel.js';
import {joinEvidence} from '../api/property-network.js';
const read=(name)=>JSON.parse(readFileSync('evidence/data/'+name,'utf8'));
const input={seed:read('imagery_manifest.json'),rings:read('outward_ring_candidates.json'),
 checks:read('fast_validation_report.json'),permits:read('municipal_permit_export_audit.json'),
 roof:read('roof_evidence_scores.json'),valuations:read('live_property_enrichment.json'),
 storm:read('noaa_storm_events_scoped.json')};
test('NOAA archive calendar dates are ISO sortable without false UTC conversion',()=>{
 assert.equal(calendarDate('19-JUN-26 17:00:00'),'2026-06-19');
 assert.equal(calendarDate('01-JAN-25 00:30:00'),'2025-01-01');
 assert.equal(calendarDate('2025-06-20'),'2025-06-20');
 assert.equal(calendarDate('2026-02-30'),null);
 assert.equal(calendarDate('Invalid'),null);
});
test('latest observed storm date wins over proximity, not a claimed roof hit',()=>{
 const s=stormCardFacts([
   {id:'near-old',kind:'HAIL',date:'01-JUN-24 10:00:00',sortKey:'2024-06-01T10:00:00',distanceKm:0.3,hailInches:2.0,windMph:null},
   {id:'far-new',kind:'THUNDERSTORM WIND',date:'19-JUN-26 17:00:00',sortKey:'2026-06-19T17:00:00',distanceKm:11.2,hailInches:null,windMph:67}
 ],true);
 assert.equal(s.latestEventId,'far-new');assert.equal(s.latestDate,'2026-06-19');
 assert.equal(s.latestDistanceKm,11.2);assert.equal(s.maxNearbyHailInches,2);
 assert.equal(s.propertyImpactVerified,false);
});
test('city issuer report date is not a completed roof replacement date',()=>{
 const p=permitCardFacts([
   {number:'2506-00458-BL',issuedAt:'2025-06-20',kind:'ROOF_CANDIDATE_PENDING_DOCUMENT_REVIEW'},
   {number:'2501-A',issuedAt:'2025-01-04',kind:'OTHER_PERMIT_TYPE'}
 ]);
 assert.equal(p.latestDate,'2025-06-20');assert.equal(p.reroofCandidateDate,'2025-06-20');
 assert.equal(p.latestNumber,'2506-00458-BL');assert.equal(p.finalInspectionVerified,false);
 assert.equal(p.verifiedRoofReplacementDate,null);
 const roof=roofReviewNeeds({yearBuilt:1993,permitFacts:p,stormFacts:stormCardFacts([],true)});
 assert.match(roof.headline,/reroof permit/i);
 assert.equal(roof.roofAgeYears,null);assert.equal(roof.roofReplacementRequired,null);
 assert.equal(roof.roofRepairRequired,null);assert.equal(roof.conditionCertified,false);
});
test('missing export and storm reports never become no-permit or no-storm certifications',()=>{
 const p=permitCardFacts([]);
 const s=stormCardFacts([],true);
 assert.equal(p.count,0);assert.equal(p.fullHistoryVerified,false);assert.equal(p.latestDate,null);
 assert.equal(s.latestDate,null);assert.equal(s.propertyImpactVerified,false);
 const needs=roofReviewNeeds({yearBuilt:1970,permitFacts:p,stormFacts:s});
 assert.ok(needs.needs.some(x=>x.code==='PERMIT_HISTORY'));
 assert.ok(needs.needs.some(x=>x.code==='ROOF_AGE'));
 assert.ok(needs.needs.some(x=>x.code==='INSPECTION'));
});
test('the real issuer roof candidate and the full GIS roster produce dated cards',()=>{
 const doc=joinEvidence(input);
 assert.equal(doc.records.length,60+input.rings.candidate_count);
 assert.equal(doc.counts.municipalReportPermits,25);
 assert.equal(doc.counts.roofReviewTasks,doc.records.length);
 const roof=doc.records.find(p=>p.id==='44018');
 assert.ok(roof,'Official city roof candidate exists');
 assert.equal(roof.permitFacts.reroofCandidateNumber,'2506-00458-BL');
 assert.equal(roof.permitFacts.reroofCandidateDate,'2025-06-20');
 assert.equal(roof.permitFacts.verifiedRoofReplacementDate,null);
 assert.ok(doc.records.every(p=>p.permitFacts&&p.stormFacts&&p.roofNeeds&&
   p.roofNeeds.conditionCertified===false&&p.roofNeeds.roofAgeYears===null));
 assert.ok(doc.records.every(p=>!p.stormFacts.latestDate||/^\d{4}-\d{2}-\d{2}$/.test(p.stormFacts.latestDate)));
 assert.ok(doc.records.every(p=>!p.permitFacts.latestDate||/^\d{4}-\d{2}-\d{2}$/.test(p.permitFacts.latestDate)));
 assert.ok(doc.counts.datedPermitReportProperties>0);
 assert.ok(doc.counts.datedStormProximityProperties>0);
});
test('the deployed React list renders all three dated evidence summaries on its actual cards',()=>{
 const source=readFileSync('frontend/src/App.jsx','utf8');
 assert.match(source,/function PropertyIndexCards/);
 assert.match(source,/permit\.latestDate/);
 assert.match(source,/storm\.latestDate/);
 assert.match(source,/roof\.headline/);
 assert.match(source,/ROOF REVIEW NEEDS/);
 assert.match(source,/No export match/);
 assert.match(source,/Not a confirmed property hit/);
 assert.ok(source.includes('<PropertyIndexCards records={filtered} onPick={select} pageSize={48}/>'));
});
