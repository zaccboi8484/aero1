/**
 * Source adapter contract taken from AeroLeadAI Core Architect's
 * PropertyEnrichmentProvider / IntelligenceProvider separation.
 * Unlike the Android sample's LocalSignalProvider, this module never fabricates signals.
 * Node 20+, no dependencies, no credentials and no network side effects.
 */
export const SIGNAL_TYPES=Object.freeze(['ROOF_AGE','STORM_EXPOSURE','TARGET_PROFILE','PROPERTY_VALUE','ROOF_PERMIT','DRIVEWAY_PERMIT','TREE_RECORD','AERIAL_IMAGE']);
export function requireHttps(url) {
 const u=new URL(url);if(u.protocol!=='https:')throw new Error('Source URL must use HTTPS');return u.toString();
}
export function normalizeAdapterRecord(record) {
 if(!record||typeof record!=='object')throw new Error('Source record required');
 const sourceUrl=requireHttps(record.source_url);
 if(!String(record.source_record_id||'').trim())throw new Error('Source record identifier required');
 if(!String(record.parcel_id||'').trim())throw new Error('Parcel ID required');
 if(!String(record.observed_at||'').trim())throw new Error('Observation timestamp required');
 if(!SIGNAL_TYPES.includes(record.signal_type))throw new Error('Unknown signal type');
 const value=Number(record.value),confidence=Number(record.confidence);
 if(!Number.isFinite(value)||value<0||value>100)throw new Error('Evidence value must be 0..100');
 if(!Number.isFinite(confidence)||confidence<0||confidence>1)throw new Error('Confidence must be 0..1');
 const status=String(record.verification_status||'UNVERIFIED').toUpperCase();
 if(!['UNVERIFIED','SOURCE_CONFIRMED','REVIEWED','REJECTED'].includes(status))throw new Error('Unknown verification status');
 return Object.freeze({
  parcel_id:String(record.parcel_id),source_record_id:String(record.source_record_id),
  source_url:sourceUrl,observed_at:String(record.observed_at),signal_type:record.signal_type,
  value,confidence,verification_status:status,
  original_source:String(record.original_source||''),
  notes:String(record.notes||'')
 });
}
export async function runAdapters({property,adapters,now=new Date().toISOString()}){
 if(!property?.parcel_id)throw new Error('Property with parcel_id required');
 const results=[],errors=[];
 for(const adapter of adapters){
  if(typeof adapter?.enrich!=='function'){errors.push({adapter:adapter?.name||'unknown',error:'Missing enrich function'});continue}
  try {
   const raw=await adapter.enrich(property,{now});
   if(!Array.isArray(raw))throw new Error('Adapter must return an array');
   for(const record of raw){try{
    const validated=normalizeAdapterRecord(record);
    if(validated.parcel_id!==String(property.parcel_id))throw new Error('Parcel mismatch');
    results.push(validated);
   }catch(error){errors.push({adapter:adapter.name||'unknown',error:String(error.message||error)})}}
  }catch(error){errors.push({adapter:adapter.name||'unknown',error:String(error.message||error)})}
 }
 return {parcel_id:String(property.parcel_id),records:results,errors,verified_signals:results.filter(r=>r.verification_status==='REVIEWED')};
}
export function scoreReviewedSignals(records){
 // Original scoring weights, applied only to validated REVIEWED provenance-backed evidence.
 const weights={ROOF_AGE:.35,STORM_EXPOSURE:.25,TARGET_PROFILE:.20,PROPERTY_VALUE:.20};
 const eligible=records.filter(r=>r.verification_status==='REVIEWED'&&weights[r.signal_type]>0);
 if(!eligible.length)return {score:null,confidence:null,status:'NOT_SCORED',reasons:[]};
 const denom=eligible.reduce((s,r)=>s+weights[r.signal_type],0);
 const num=eligible.reduce((s,r)=>s+weights[r.signal_type]*r.value*r.confidence,0);
 return {score:Math.round(Math.min(100,Math.max(0,num/denom))),confidence:Math.round(100*eligible.reduce((s,r)=>s+r.confidence,0)/eligible.length),status:'REVIEWED_INPUTS_ONLY',reasons:eligible.map(r=>r.signal_type)};
}
