import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFileSync} from 'node:fs';

test('Vercel build preserves the original interface while fixing evidence live-sync',()=>{
 execFileSync(process.execPath,['scripts/build-web.mjs'],{encoding:'utf8'});
 const dashboard=readFileSync('public/index.html','utf8');
 const source=readFileSync('index.html','utf8');
 const cards=readFileSync('public/roofing-scorecards.html','utf8');
 const sync=readFileSync('public/live-sync.js','utf8');
 assert.ok(source.length>50000,'Original UI source must exist');
 assert.ok(dashboard.includes('<script src="/live-sync.js" defer></script>'));
 assert.ok(cards.includes('<script src="/live-sync.js" defer></script>'));
 assert.ok(cards.includes('Residential Roofing Scorecards'));
 assert.ok(dashboard.includes('Array.isArray(j.records)?j.records:Array.isArray(j.properties)?j.properties:[]'),
  'Roofing outreach must iterate records rather than numeric properties count');
 assert.ok(dashboard.includes("document.getElementById('permitCount').textContent=String(j.matched_permit_events??0)"),
  'Permit dashboard must display real imported municipal match count');
 assert.ok(dashboard.includes('cineOrbit')&&dashboard.includes('requestAnimationFrame'),
  'Do not remove cinematic map and interactive orbit code');
 assert.ok(dashboard.includes('aerialImage')&&dashboard.includes('glassModeToggle'),
  'Do not remove real aerial imagery and glass UI');
 assert.ok(dashboard.includes('/api/auth')&&cards.includes('/api/roofing-scorecards'),
  'Retain secured application routing');
 assert.ok(sync.includes('source_health_public.json')&&sync.includes('PUBLIC_SOURCE_UNAVAILABLE'));
 assert.ok(!sync.includes('roof_condition_score=100'),'Never invent roof conditions');
});
