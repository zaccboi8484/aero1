// GateKeeper: deterministic deployment packaging. Preserve the evidence registry
// and original viewer; fix known live-only defects without rewriting source HTML.
import {readFileSync,writeFileSync,copyFileSync,mkdirSync} from 'node:fs';
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
writeFileSync(join(out,'index.html'),home,'utf8');
let cards=readFileSync('roofing-scorecards.html','utf8');
cards=attachSync(cards,'scorecards');
writeFileSync(join(out,'roofing-scorecards.html'),cards,'utf8');
copyFileSync('luckyg-core.js',join(out,'luckyg-core.js'));
console.log('AeroLeadAI deploy build: existing dashboards + zoom/viewer retained; roofing list and permit counters fixed; live evidence synchronization installed.');
