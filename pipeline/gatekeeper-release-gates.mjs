/**
 * GateKeeper / AeroLeadAI release standards v1
 * Ten executable acceptance contracts; real-source evidence only.
 * Run tests: node pipeline/gatekeeper-release-gates.mjs
 */
import assert from 'node:assert/strict';

export const STANDARDS=Object.freeze({
 provenance:'Evidence requires an original source URL, source record identifier and acquisition time.',
 uncertainty:'Unknown does not mean none, zero, or safe. Never turn missing evidence into a negative finding.',
 access:'Use authorized source endpoints; do not evade site access controls or expose API credentials.',
 identity:'Match permits, images and events to a specific parcel using traceable identifiers.',
 separation:'Separate raw evidence, user memory notes, model inference and approved findings.',
 scoring:'Only reviewed inputs enter Mindex; valuations and opportunity scores remain distinct.',
 audit:'Every status transition records run ID, timestamp, evidence IDs and reason.',
 expansion:'Ring candidates are leads until mapped and checked; expansion must deduplicate PINs.',
 chat:'LuckyG retrieves grounded cards without claiming unsupported internet access.',
 release:'An update is implemented only after automated tests and real-world evidence checks.'
});

export const UPDATES=Object.freeze([
 {id:'01_PARCELS',name:'First 60 parcel geometry and subdivision joins',fields:['parcel_id','official_source_url','geometry_match','queried_at'],block:['inferred_subdivision_membership']},
 {id:'02_PERMITS',name:'Authorized Eagan permit searches per address',fields:['parcel_id','searched_at','source_url','result_status'],block:['403_bypass','missing_means_no_permits']},
 {id:'03_VALUES',name:'Official assessment value enrichment',fields:['parcel_id','valuation_source','assessment_year','amount_or_unavailable'],block:['missing_value_as_zero']},
 {id:'04_STORMS',name:'Storm histories and parcel proximity',fields:['parcel_id','event_id','event_date','location_match','source_url'],block:['weather_means_damage']},
 {id:'05_IMAGERY',name:'Authorized historical imagery acquisition',fields:['parcel_id','image_source','capture_date_or_unknown','image_status'],block:['invalid_image_as_downloaded','google_streetview_scraping']},
 {id:'06_EVIDENCE',name:'GateKeeper provenance and contradiction review',fields:['claim_id','source_record_ids','contradictions','review_status'],block:['unverified_as_proven']},
 {id:'07_MINDEX',name:'Explainable property and opportunity scoring',fields:['parcel_id','mindex_or_null','valuation_or_null','score_version'],block:['placeholder_score']},
 {id:'08_LUCKYG',name:'Card-index chat, memory and voice access',fields:['input_query','matched_parcel_or_not_found','voice_permission_status','memory_export_status'],block:['invented_lookup']},
 {id:'09_RINGS',name:'Continuing parcel-by-parcel expansion',fields:['ring_id','official_boundary','cursor','deduped_parcel_ids'],block:['duplicate_as_new_property']},
 {id:'10_HEALTH',name:'Self-auditing scheduled sources and recovery',fields:['run_id','source_attempts','outcomes','next_retry','audit_event_hash'],block:['silent_failure']}
]);

export function validateGate(id,report={}){
 const gate=UPDATES.find(u=>u.id===id);
 if(!gate)throw Error('Unknown GateKeeper gate');
 const missing=gate.fields.filter(k=>!Object.hasOwn(report,k)||report[k]===undefined||report[k]===null||report[k]==='');
 const violations=(report.violations||[]).filter(x=>gate.block.includes(x));
 const executable=report.tests_passed===true;
 const reviewed=report.provenance_reviewed===true;
 const passed=missing.length===0&&violations.length===0&&executable&&reviewed;
 return {gate:id,passed,missing,violations,status:passed?'REVIEWED_GATE_PASSED':'NOT_COMPLETED'};
}
if(process.argv[1]&&import.meta.url===new URL('file://'+process.argv[1]).href){
 assert.equal(UPDATES.length,10);
 assert.equal(validateGate('02_PERMITS',{}).passed,false);
 assert.equal(validateGate('07_MINDEX',{parcel_id:'1',mindex_or_null:0,valuation_or_null:0,score_version:'1',tests_passed:true,provenance_reviewed:true,violations:['placeholder_score']}).passed,false);
 console.log('GateKeeper release contract tests passed; none of the ten releases is thereby certified.');
}
