import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {joinEvidence} from '../api/property-network.js';
const path=name=>'evidence/data/'+name;
const read=(name,optional=false)=>{try{return JSON.parse(readFileSync(path(name),'utf8'))}catch(e){if(optional&&e.code==='ENOENT')return null;throw e}};
const data={
 seed:read('imagery_manifest.json'),rings:read('outward_ring_candidates.json'),
 checks:read('fast_validation_report.json'),permits:read('municipal_permit_export_audit.json'),
 roof:read('roof_evidence_scores.json'),valuations:read('live_property_enrichment.json'),
 storm:read('noaa_storm_events_scoped.json',true)
};
test('real official GIS source joins seed and uncapped outward parcels',()=>{
 const result=joinEvidence(data);
 assert.equal(result.counts.initialBatch,60);
 assert.equal(result.counts.expansion,data.rings.candidate_count);
 assert.equal(result.counts.parcels,60+data.rings.candidate_count);
 assert.ok(result.counts.parcels>=417,'Original source network already contained 417 distinct parcels');
 assert.equal(new Set(result.records.map(x=>x.pin)).size,result.counts.parcels);
 assert.ok(result.records.some(x=>x.ring>0));
 assert.equal(result.counts.parcelsAttemptedAtLeastOnce+result.counts.parcelsNeverAttempted,
  result.counts.parcels);
 assert.ok(result.counts.parcelsNeverAttempted>=0);
});
test('real city export matches survive, city history and roof condition still not certified',()=>{
 const result=joinEvidence(data);
 assert.equal(result.counts.municipalReportPermits,25);
 assert.equal(result.counts.municipalReportProperties,18);
 assert.equal(result.counts.certifiedRoofConditions,0);
 assert.ok(result.records.every(x=>x.completeMunicipalPermitHistory===false&&
    x.roofConditionScore===null&&x.gatekeeperCertified===false));
 assert.ok(result.records.filter(x=>x.ring>0).every(x=>x.researchPriority===null));
});
test('GIS PIN identity contradiction causes a hard failure',()=>{
 const faulty={...data,rings:{...data.rings,ring_candidates:[...data.rings.ring_candidates]}};
 faulty.rings.ring_candidates[0]={...faulty.rings.ring_candidates[0],county_pin:data.seed.records[0].county_pin};
 assert.throws(()=>joinEvidence(faulty),/contradictory identity/);
});
test('NOAA storm records do not create a parcel storm-hit or damage score',()=>{
 const result=joinEvidence(data);
 if(data.storm){assert.equal(result.counts.historicalStormReports,data.storm.events.length);
  assert.ok(result.records.every(p=>p.stormReports.every(e=>e.relation==='NEARBY_REPORT_NOT_PROPERTY_IMPACT')))}
 else assert.equal(result.counts.historicalStormReports,0);
});
