// The coordinator is the only pipeline component allowed to mark a job completed and write audit history.
export function validateObservation(job, observation) {
  if (!job?.id || !job?.territory || !job?.source_key) throw new Error('Invalid job');
  if (!observation || typeof observation !== 'object') throw new Error('Missing observation');
  if (observation.territory !== job.territory) throw new Error('Territory mismatch');
  if (observation.source_key !== job.source_key) throw new Error('Source mismatch');
  if (typeof observation.source_url !== 'string' || !/^https:\/\//.test(observation.source_url)) throw new Error('Missing HTTPS provenance');
  if (typeof observation.source_record_id !== 'string' || !observation.source_record_id.trim()) throw new Error('Missing source ID');
  return {
    job_id: job.id,
    territory: job.territory,
    source_key: job.source_key,
    source_url: observation.source_url,
    source_record_id: observation.source_record_id,
    verification_status: 'UNVERIFIED',
    classification: 'REAL-NOW',
    findings: { raw_source_record: observation.data ?? null, gatekeeper_note: 'Observed source data only; no property condition inferred' }
  };
}
export async function coordinate({ db, job, observation }) {
  const audit = validateObservation(job, observation);
  const { error } = await db.from('aero_crawl_audit').upsert(audit,{onConflict:'job_id'});
  if (error) throw error;
  const { error: completedError } = await db.from('aero_crawl_jobs').update({
    status:'completed',lease_until:null,updated_at:new Date().toISOString()
  }).eq('id',job.id).eq('status','processing').eq('worker_id',job.worker_id);
  if (completedError) throw completedError;
  return audit;
}
