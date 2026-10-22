import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {canonicalInventory,parseResponse} from '../scripts/verify_parcels_bulk.mjs';
const dir='evidence/data/';
const seed=JSON.parse(readFileSync(dir+'imagery_manifest.json'));
const rings=JSON.parse(readFileSync(dir+'outward_ring_candidates.json'));
test('bulk verifier covers all source-discovered parcels beyond the initial 60',()=>{
 const a=canonicalInventory(seed,rings);
 assert.equal(a.length,60+rings.candidate_count);
 assert.ok(a.length>400);
 assert.equal(new Set(a.map(x=>x.county_pin)).size,a.length);
});
test('exact official ArcGIS returns must match all requested PINs',()=>{
 const p=new Set(['104200101010','104200101020']);
 const exact=parseResponse({features:[{attributes:{OBJECTID:44001,COUNTY_PIN:'104200101010'}},
 {attributes:{OBJECTID:44002,COUNTY_PIN:'104200101020'}}]},p);
 assert.equal(exact.size,2);
 assert.throws(()=>parseResponse({features:[{attributes:{OBJECTID:44001,COUNTY_PIN:'104200101010'}}]},p),/not returned/);
 assert.throws(()=>parseResponse({exceededTransferLimit:true,features:[]},p),/truncated/);
 assert.throws(()=>parseResponse({features:[{attributes:{OBJECTID:44001,COUNTY_PIN:'104200101010'}},
 {attributes:{OBJECTID:44002,COUNTY_PIN:'104200101010'}}]},new Set(['104200101010'])),/Duplicate/);
});
test('the registry cannot silently add fake PINs or collapse 60 into the whole project',()=>{
 const tampered={...rings,ring_candidates:[...rings.ring_candidates]};
 tampered.ring_candidates[0]={...tampered.ring_candidates[0],county_pin:seed.records[0].county_pin};
 assert.throws(()=>canonicalInventory(seed,tampered),/Duplicate/);
});
