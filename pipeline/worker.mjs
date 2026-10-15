// Run out-of-band (not inside a browser or request handler).
// HTTPS source URL must be explicitly configured and approved.
import { createClient } from '@supabase/supabase-js';
import { randomUUID } from 'node:crypto';
import { coordinate } from './coordinator.mjs';
const required = ['SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY','CRAWLER_SOURCE_URL'];
for (const k of required) if (!process.env[k]) throw new Error('Missing '+k);
const approved = new URL(process.env.CRAWLER_SOURCE_URL);
if (approved.protocol !== 'https:') throw new Error('HTTPS-only source');
const db=createClient(process.env.SUPABASE_URL,process.env.SUPABASE_SERVICE_ROLE_KEY,{
  auth:{persistSession:false,autoRefreshToken:false}
});
const worker='aero-worker-'+randomUUID();
const {data,error}=await db.rpc('aero_claim_job',{p_worker:worker,p_lease_seconds:120});
if(error) throw error;
const job=data?.[0];
if(!job){console.log('Queue empty');process.exit(0)}
try{
  const url=new URL(approved);
  // Deliberately constrained to the configured source host and path.
  if (job.request?.query) url.searchParams.set('where',String(job.request.query));
  const resp=await fetch(url,{signal:AbortSignal.timeout(15000),headers:{accept:'application/json'}});
  if(!resp.ok) throw new Error('Source HTTP '+resp.status);
  const body=await resp.json();
  const sourceRecord=body?.features?.[0]?.attributes ?? body?.records?.[0] ?? null;
  if(!sourceRecord) throw new Error('No source record returned');
  const sourceId=sourceRecord.OBJECTID ?? sourceRecord.objectid ?? sourceRecord.id;
  if(sourceId===undefined)throw new Error('Missing source record ID');
  await coordinate({db,job,observation:{
    territory:job.territory,source_key:job.source_key,
    source_url:url.toString(),source_record_id:String(sourceId),data:sourceRecord
  }});
  console.log('Processed',job.id);
}catch(err){
  const retry=job.attempts<job.max_attempts;
  const {error:updateErr}=await db.from('aero_crawl_jobs').update({
    status:retry?'queued':'failed',lease_until:null,worker_id:null,
    available_at:new Date(Date.now()+Math.min(3600000,2**job.attempts*30000)).toISOString(),
    last_error:String(err).slice(0,500),updated_at:new Date().toISOString()
  }).eq('id',job.id).eq('worker_id',worker);
  if(updateErr)throw updateErr;
  console.error('Crawler failed:',String(err));
  process.exitCode=1;
}
