import test from 'node:test';
import assert from 'node:assert/strict';
import {guard} from '../security/apiGuard.mjs';

const configured={AEROLEADAI_API_KEYS:'old-key,new-key',
 ALLOWED_ORIGINS:'https://aeroleadaigithubreadyv03.vercel.app'};
const request=(headers={})=>new Request('https://example.invalid/api',{
 method:'POST',headers
});
test('fails closed if no API keys',()=>assert.equal(guard(request(),{}).status,503));
test('rejects wildcard origin configuration',()=>assert.equal(guard(request(),{...configured,ALLOWED_ORIGINS:'*'}).status,503));
test('requires bearer token',()=>assert.equal(guard(request(),configured).status,401));
test('rejects wrong bearer token',()=>assert.equal(guard(request({authorization:'Bearer bad'}),configured).status,401));
test('denies untrusted browser origin',()=>assert.equal(guard(request({authorization:'Bearer new-key',origin:'https://malicious.invalid'}),configured).status,403));
test('allows supported token rotation from approved origin',()=>{
 for(const key of ['old-key','new-key'])
  assert.equal(guard(request({authorization:'Bearer '+key,origin:'https://aeroleadaigithubreadyv03.vercel.app'}),configured),null);
});
test('same bearer key without valid configured origin cannot bypass',()=>{
 assert.equal(guard(request({authorization:'Bearer old-key',origin:'null'}),configured).status,403);
});
