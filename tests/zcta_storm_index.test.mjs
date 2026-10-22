import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {ringContains,zctaAt,normalizeNoaaDate,validateCensusGeo,makeZipStormIndex} from '../scripts/build_zip_storm_index.mjs';

const box=(xmin,ymin,xmax,ymax)=>[[xmin,ymin],[xmax,ymin],[xmax,ymax],[xmin,ymax],[xmin,ymin]];
const census={features:[{
 attributes:{ZCTA5:'55121'},
 geometry:{rings:[box(-93.5,44.6,-92.7,45.1),box(-93.0,44.9,-92.95,44.95)]}
}]};

test('ZIP-area match uses official Census polygon, not city or 15km proximity',()=>{
 const shapes=validateCensusGeo(census);
 assert.equal(zctaAt(-93.16,44.81,shapes),'55121');
 assert.equal(zctaAt(-92.97,44.92,shapes),null,'Excluded Census polygon hole');
 assert.equal(zctaAt(-93.65,44.81,shapes),null);
 assert.ok(ringContains(-93.17,44.82,box(-93.5,44.6,-92.7,45.1)));
});
test('NOAA original report date is normalized without inventing a UTC timezone',()=>{
 assert.deepEqual(normalizeNoaaDate('31-JUL-24 17:30:00'),
  {date:'2024-07-31',localTime:'17:30:00',original:'31-JUL-24 17:30:00'});
 assert.equal(normalizeNoaaDate('2025-06-20').date,'2025-06-20');
 assert.equal(normalizeNoaaDate('bad').date,null);
});
test('truncated, ambiguous, or imaginary ZIP geometry cannot be accepted',()=>{
 assert.throws(()=>validateCensusGeo({exceededTransferLimit:true,features:census.features}),/truncated/);
 assert.throws(()=>validateCensusGeo({features:[...census.features,...census.features]}),/duplicate/);
 assert.throws(()=>validateCensusGeo({features:[]}),/empty/);
});
test('real 60 plus ring data joins NOAA point records with ZIP date, never a house hit',()=>{
 const read=name=>JSON.parse(readFileSync('evidence/data/'+name,'utf8'));
 const seed=read('imagery_manifest.json'),rings=read('outward_ring_candidates.json'),noaa=read('noaa_storm_events_scoped.json');
 const output=makeZipStormIndex({seed,rings,noaa,census});
 assert.equal(output.parcel_count,60+rings.candidate_count);
 assert.ok(output.parcel_count>400);
 assert.ok(output.parcels_mapped>60);
 assert.equal(output.not_a_property_storm_damage_certification,true);
 assert.ok(output.parcels.every(x=>x.no_usps_delivery_verification===true));
 assert.ok(output.events_by_zip.every(x=>x.reports.every(e=>
 e.report_classification==='NWS_REPORTED_POINT_WITHIN_CENSUS_ZCTA'&&
 e.not_confirmed_at_any_particular_roof===true&&/^\d{4}-\d\d-\d\d$/.test(e.date))));
});
test('NOAA county-only observations are not ZIP hits',()=>{
 const seed={records:[{parcel_objectid:'1',county_pin:'123456789',center_lat:44.81,center_lon:-93.16}]};
 const rings={candidate_count:0,ring_candidates:[],source_query_completed:true,errors:[]};
 // Real production requires 60; replace with 60 different IDs and PINs.
 seed.records=Array.from({length:60},(_,i)=>({...seed.records[0],parcel_objectid:String(i+1),county_pin:String(123456789+i)}));
 const noaa={format:'GATEKEEPER_NOAA_STORM_EVENTS_V1',retrieved_at_utc:'2026-10-22T00:00:00Z',
 report_count:1,partial:false,events:[{id:'N-1',kind:'HAIL',begin_at:'31-JUL-24 17:30:00',point_lat:null,point_lon:null}]};
 const o=makeZipStormIndex({seed,rings,noaa,census});
 assert.equal(o.event_points_in_scope,0);
 assert.equal(o.events_without_zip_point,1);
});
