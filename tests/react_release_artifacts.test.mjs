import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync,existsSync} from 'node:fs';
test('build emits compiled React entrypoint and preserves existing source-evidence views',()=>{
 const html=readFileSync('public/index.html','utf8');
 assert.match(html,/AeroLeadAI · Property Intelligence/);
 assert.match(html,/src="\/assets\/[^"]+\.js"/);
 const js=readdirSync('public/assets').filter(x=>x.endsWith('.js'));
 assert.ok(js.length>0);
 assert.match(js.map(name=>readFileSync('public/assets/'+name,'utf8')).join(''),/GateKeeper|GATEKEEPER|AeroLeadAI/);
 for(const page of ['classic.html','certification-gaps.html','roofing-scorecards.html','network.html'])
  assert.ok(existsSync('public/'+page),'Must preserve '+page);
 assert.match(readFileSync('public/classic.html','utf8'),/cineOrbit/);
 assert.ok(!html.includes('base44.app'));
});
