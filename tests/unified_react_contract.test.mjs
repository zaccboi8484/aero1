import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {classifySource} from '../api/operations-health.js';
test('live app uses compiled React and has no Base44 SDK',()=>{
 const a=readFileSync('frontend/src/App.jsx','utf8'),pkg=readFileSync('package.json','utf8'),
  html=readFileSync('frontend/index.html','utf8');
 assert.match(a,/React,/);assert.match(a,/GeoMap/);assert.match(a,/PermitPanel/);
 assert.match(a,/StormPanel/);assert.match(a,/SourceMeter/);
 assert.match(a,/NOAA REPORTED POINT IN ZIP-AREA/);
 assert.match(a,/zipAreaStormReports/);
 assert.match(a,/PropertyIndexCards/);
 assert.match(a,/api[/]property-network/);
 assert.match(html,/\/src\/main.jsx/);
 assert.equal(/@base44|base44\/sdk|base44\.app/i.test(pkg+a+html),false);
});
test('source states are not a false green when city portal blocked or NOAA partial',()=>{
 const now=Date.parse('2026-10-22T20:00:00Z');
 const storm={id:'storm',hours:40,timestamp:'retrieved_at_utc',message:'real observations'};
 assert.equal(classifySource(storm,{retrieved_at_utc:'2026-10-22T19:00:00Z'},now).state,'CURRENT');
 assert.equal(classifySource(storm,{retrieved_at_utc:'2026-10-22T19:00:00Z',partial:true},now).state,'DEGRADED');
 assert.equal(classifySource(storm,{retrieved_at_utc:'2026-10-19T19:00:00Z'},now).state,'STALE');
 assert.equal(classifySource(storm,null,now).state,'UNAVAILABLE');
 assert.equal(classifySource({id:'permits'},{matched_permit_events:25,generated_at_utc:'2026-10-17T11:00:00Z'}).state,'BLOCKED');
});
