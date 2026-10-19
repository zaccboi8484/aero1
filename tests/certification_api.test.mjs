import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {createHmac} from 'node:crypto';

// Fixture is generated from REAL committed first-60 evidence, not imagined records.
// It never attempts to access Eagan's restricted portal.
execFileSync('python3',['collector/certification_gap_pipeline.py'],{encoding:'utf8'});
const summary=JSON.parse(readFileSync('evidence/data/certification_gap_summary.json','utf8'));
const queue=JSON.parse(readFileSync('evidence/data/certification_gap_queue.json','utf8'));
const prior={pass:process.env.AERO_ACCESS_PASSCODE,secret:process.env.AERO_SESSION_SECRET,fetch:globalThis.fetch};
process.env.AERO_ACCESS_PASSCODE='unit-test-only-not-a-real-passcode';
process.env.AERO_SESSION_SECRET='unit-test-only-not-a-real-secret';
globalThis.fetch=async url=>{
 const data=String(url).includes('certification_gap_summary.json')?summary:queue;
 return {ok:true,json:async()=>structuredClone(data)};
};
const {default:handler}=await import('../api/certification-gaps.js');
function request(query={},cookie=''){
 return {method:'GET',query,headers:{cookie}};
}
function mock(){
 let statusCode=0,body=null;
 return {setHeader(){},status(code){statusCode=code;return this},json(data){body=data;return this},
  output(){return {statusCode,body}}};
}
const token=()=>{
 const exp=String(Date.now()+3600000);
 const mac=createHmac('sha256',process.env.AERO_SESSION_SECRET).update(exp).digest('base64url');
 return 'aero_session='+exp+'.'+mac;
};
test('GateKeeper denies anonymous certification searches',async()=>{
 const res=mock();await handler(request(),res);
 assert.equal(res.output().statusCode,401);
 assert.match(res.output().body.error,/session required/);
});
test('Authorized search returns source-backed 60 and leaves certification at zero',async()=>{
 const res=mock();await handler(request({limit:'100' },token()),res);
 const {statusCode,body}=res.output();
 assert.equal(statusCode,200);
 assert.equal(body.summary.original_residential_parcels,60);
 assert.equal(body.summary.export_report_matches_pending_document_review,25);
 assert.equal(body.summary.priority_roof_2025_candidates,1);
 assert.equal(body.summary.certified_mindex_scores,0);
 assert.equal(body.summary.original_issuer_permit_documents_reviewed,0);
 assert.equal(body.returned,100);
 assert.equal(body.status,'SOURCE_BACKED_RESEARCH_QUEUE_NOT_CERTIFICATION');
 assert.ok(body.records.every(x=>!x.completed&&!x.certification_approved));
});
test('Permit number filtering returns its exact City-report candidate only',async()=>{
 const res=mock();await handler(request({limit:'100',q:'2506-00458-BL'},token()),res);
 const {statusCode,body}=res.output();
 assert.equal(statusCode,200);assert.equal(body.total_matches,1);
 assert.equal(body.records[0].parcel_objectid,'44018');
 assert.equal(body.records[0].kind,'ORIGINAL_ISSUER_PERMIT_DOCUMENT');
});
test('Filters do not pretend a missing permit match is a verified no-permit outcome',async()=>{
 const res=mock();await handler(request({kind:'MUNICIPAL_FULL_PERMIT_HISTORY',limit:'100'},token()),res);
 const {body}=res.output();assert.equal(body.total_matches,60);
 assert.ok(body.records.every(x=>x.status==='SOURCE_BLOCKED'||x.status==='AWAITING_AUTHORIZED_PROVIDER'));
});
test.after(()=>{
 if(prior.pass===undefined)delete process.env.AERO_ACCESS_PASSCODE;else process.env.AERO_ACCESS_PASSCODE=prior.pass;
 if(prior.secret===undefined)delete process.env.AERO_SESSION_SECRET;else process.env.AERO_SESSION_SECRET=prior.secret;
 globalThis.fetch=prior.fetch;
});
