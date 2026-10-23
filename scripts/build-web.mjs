// GateKeeper: deterministic deployment packaging. Preserve the evidence registry
// and original viewer; fix known live-only defects without rewriting source HTML.
import {readFileSync,writeFileSync,copyFileSync,mkdirSync,existsSync} from 'node:fs';
import {join} from 'node:path';
const out='public';
mkdirSync(out,{recursive:true});
const requireOnce=(s,needle,label)=>{
 const count=s.split(needle).length-1;
 if(count!==1)throw Error(label+': expected one exact source anchor; found '+count);
 return s;
};
function attachSync(html,label){
 requireOnce(html,'</body>',label+' document end');
 return html.replace('</body>','<script src="/live-sync.js" defer></script></body>');
}
let home=readFileSync('index.html','utf8');
const priorityBug='j.properties||j.records||[]';
requireOnce(home,priorityBug,'roofing priority record iterator');
home=home.replace(priorityBug,'(Array.isArray(j.records)?j.records:Array.isArray(j.properties)?j.properties:[])');
const permitMarker='municipalExportSummary=j;';
requireOnce(home,permitMarker,'municipal permit reporting');
home=home.replace(permitMarker,permitMarker+"document.getElementById('permitCount').textContent=String(j.matched_permit_events??0);");
home=attachSync(home,'home');
// Original glass desk remains accessible, but the uncapped real GIS property
// network is now the default screen. The first 60 are a seed batch, NOT a cap.
writeFileSync(join(out,'classic.html'),home,'utf8');
const network=readFileSync('network.html','utf8');
requireOnce(network,'</body>','network page');
writeFileSync(join(out,'index.html'),network,'utf8');
writeFileSync(join(out,'network.html'),network,'utf8');
copyFileSync('network.js',join(out,'network.js'));
copyFileSync('mindex-browser.html',join(out,'mindex-browser.html'));
let cards=readFileSync('roofing-scorecards.html','utf8');
cards=attachSync(cards,'scorecards');
writeFileSync(join(out,'roofing-scorecards.html'),cards,'utf8');
// Standalone GateKeeper research console: joins published evidence without altering original pages.
copyFileSync('certification-gaps.html',join(out,'certification-gaps.html'));
copyFileSync('luckyg-core.js',join(out,'luckyg-core.js'));
// Ship the assembled Mindex intelligence with the static app so each deployment
// contains an auditable dataset, even when the optional database is unavailable.
const publicData=join(out,'data');
mkdirSync(publicData,{recursive:true});
for(const name of ['mindex_property_cards.json','roof_priority_v2.json','aerial_coverage_ledger.json','parcel_schema.json']){
 const source=join('evidence','data',name);
 if(!existsSync(source))throw Error('Required deployed evidence missing: '+source);
 copyFileSync(source,join(publicData,name));
}
const leadCsv=join('evidence','data','mindex_lead_export.csv');
if(!existsSync(leadCsv))throw Error('Required lead export missing');
copyFileSync(leadCsv,join(publicData,'mindex_lead_export.csv'));
const payload=JSON.parse(readFileSync(join(publicData,'mindex_property_cards.json'),'utf8'));
if(!Array.isArray(payload.cards)||payload.cards.length!==payload.count||payload.count===0)throw Error('Invalid Mindex deploy dataset');
console.log('Mindex static deployment dataset:',payload.count,'properties,',payload.ranked,'ranked');
console.log('AeroLeadAI deploy build: existing dashboards + zoom/viewer retained; roofing list and permit counters fixed; live evidence synchronization installed.');
