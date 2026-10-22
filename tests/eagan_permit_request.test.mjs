import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {makePacket} from '../scripts/build_eagan_permit_request.mjs';
const dir='evidence/data/';
const load=n=>JSON.parse(readFileSync(dir+n,'utf8'));
const seed=load('imagery_manifest.json'),rings=load('outward_ring_candidates.json'),
 report=load('municipal_permit_export_audit.json');
test('actual Eagan issuer records request covers every independently discovered property',()=>{
 const {csv,report:out}=makePacket(seed,rings,report);
 assert.equal(out.parcel_count,60+rings.candidate_count);
 assert.equal(out.municipal_report_matches,25);
 assert.equal(out.original_city_issuer_permit_documents_reviewed,0);
 assert.ok(csv.includes('2506-00458-BL'));
 assert.ok(csv.includes('1459 Kings Wood Lane'));
 assert.equal(csv.trimEnd().split('\n').length,out.parcel_count+1);
 assert.equal(out.not_submitted,true);
});
test('contradictory expanded GIS identity fails before external municipal request',()=>{
 const modified={...rings,ring_candidates:[...rings.ring_candidates]};
 modified.ring_candidates[0]={...modified.ring_candidates[0],county_pin:seed.records[0].county_pin};
 assert.throws(()=>makePacket(seed,modified,report),/Duplicate parcel ID\/PIN/);
});
test('incomplete ArcGIS discovery may not be called a complete city request',()=>{
 assert.throws(()=>makePacket(seed,{...rings,source_query_completed:false},report),/incomplete GIS discovery/);
});
