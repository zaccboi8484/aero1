import test from 'node:test';
import assert from 'node:assert/strict';
import {extract,csvRows,distanceKm} from '../scripts/ingest_noaa_storms.mjs';
const geo=[{lat:44.815,lon:-93.17}];
test('NOAA parses quoted storm narratives without inventing records',()=>{
 assert.deepEqual(csvRows('A,B\n1,"wind, hail\nand rain"\n'),[['A','B'],['1','wind, hail\nand rain']]);
});
test('NOAA hail inches and wind knots conversion have correct source semantics',()=>{
 const csv='EVENT_ID,STATE,EVENT_TYPE,BEGIN_DATE_TIME,END_DATE_TIME,CZ_NAME,CZ_TYPE,BEGIN_LAT,BEGIN_LON,MAGNITUDE,MAGNITUDE_TYPE,SOURCE\n1,MINNESOTA,Hail,06/01/2025,,Dakota,C,44.816,-93.17,1.75,,Trained Spotter\n2,MINNESOTA,Thunderstorm Wind,06/01/2025,,Dakota,C,44.821,-93.18,60,MG,ASOS\n3,MINNESOTA,Hail,06/01/2025,,Hennepin,C,46,-95,2,,Public\n';
 const e=extract(csv,'official-2025.csv.gz',geo,12);
 assert.equal(e.length,2);assert.equal(e[0].hail_inches,1.75);
 assert.equal(e[1].wind_mph,69);assert.equal(e[1].wind_original_knots,60);
 assert.ok(e.every(x=>x.damage_to_any_individual_property_confirmed===false));
 assert.ok(distanceKm(44.815,-93.17,44.816,-93.17)<0.2);
});
test('county-only reports are never assigned property coordinates',()=>{
 const csv='EVENT_ID,STATE,EVENT_TYPE,BEGIN_DATE_TIME,CZ_NAME,CZ_TYPE,BEGIN_LAT,BEGIN_LON,MAGNITUDE\n900,MINNESOTA,Hail,01/01/2025,Dakota,C,,,1.5\n';
 const r=extract(csv,'NOAA.csv.gz',geo);
 assert.equal(r[0].geographic_confidence,'COUNTY_REPORT_ONLY');assert.equal(r[0].point_lat,null);
});

test('NOAA DD-MON-YY local source dates retain chronologically sortable evidence keys',()=>{
 const csv='EVENT_ID,STATE,EVENT_TYPE,BEGIN_DATE_TIME,CZ_NAME,CZ_TYPE,BEGIN_LAT,BEGIN_LON,MAGNITUDE\n11,MINNESOTA,Hail,31-JUL-24 17:30:00,Dakota,C,44.8,-93.1,2\n12,MINNESOTA,Hail,01-JUN-26 17:30:00,Dakota,C,44.8,-93.1,1.5\n';
 const r=extract(csv,'official.csv.gz',geo);
 assert.equal(r[0].sort_key,'2024-07-31T17:30:00');
 assert.equal(r[1].sort_key,'2026-06-01T17:30:00');
 assert.ok(r[1].sort_key>r[0].sort_key);
});
