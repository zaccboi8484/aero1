import test from 'node:test';
import assert from 'node:assert/strict';
import handler from '../api/version.js';
test('version is GET-only, does not guess a SHA',()=>{
 const prev=process.env.VERCEL_GIT_COMMIT_SHA;
 delete process.env.VERCEL_GIT_COMMIT_SHA;
 const make=()=>({headers:{},setHeader(k,v){this.headers[k]=v},status(s){this.code=s;return this},json(d){this.body=d;return this}});
 try {
  const ok=make();handler({method:'GET'},ok);
  assert.equal(ok.code,200);assert.equal(ok.body.commit,null);assert.equal(ok.body.deployed,false);
  assert.equal(ok.headers['Cache-Control'],'no-store');
  const bad=make();handler({method:'POST'},bad);assert.equal(bad.code,405);
 }finally{if(prev!==undefined)process.env.VERCEL_GIT_COMMIT_SHA=prev}
});
