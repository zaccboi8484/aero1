import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const sql=readFileSync('supabase/migrations/007_gatekeeper_certification_receipts.sql','utf8');
test('Supabase certification migration is staged and never publicly grants reviewer data',()=>{
 assert.match(sql,/STAGED ONLY/);
 for(const table of ['aero_certification_tasks','aero_certification_review_receipts','aero_certification_release_events']){
  assert.ok(sql.includes('create table if not exists public.'+table));
  assert.ok(sql.includes('alter table public.'+table+' enable row level security'));
 }
 assert.match(sql,/revoke all on public[.]aero_certification_tasks,[\s\S]*from anon,authenticated;/);
 assert.ok(!sql.includes('grant all on public.aero_certification_review_receipts to authenticated'));
});
test('Review receipts and release decisions enforce two append-only mutation blocks',()=>{
 assert.match(sql,/create trigger aero_review_receipts_immutable/);
 assert.match(sql,/create trigger aero_release_events_immutable/);
 assert.match(sql,/before update or delete/);
 assert.match(sql,/reviewer_id <> approved_by/);
 assert.match(sql,/cardinality\(source_receipt_ids\) >= 2/);
 assert.match(sql,/issuer_document_sha256/);
 assert.match(sql,/CONFIRMED_FINAL_INSPECTION_RECORD/);
});
