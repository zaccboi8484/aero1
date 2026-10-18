// Optional fail-closed guard for future server-side paid/sensitive fetch-style API routes.
// Not wired into the existing AeroLeadAI session API or GateKeeper scorecards.
// Server-only environment: AEROLEADAI_API_KEYS="current-key,previous-key";
// ALLOWED_ORIGINS="https://aeroleadaigithubreadyv03.vercel.app".
// An Origin header is browser-supplied context, NOT authorization by itself.
import {timingSafeEqual} from 'node:crypto';

const json=(status,body,headers={})=>new Response(JSON.stringify(body),{
 status,headers:{'content-type':'application/json','cache-control':'no-store',...headers}
});
const eq=(a,b)=>{
 const A=Buffer.from(a), B=Buffer.from(b);
 return A.length===B.length&&timingSafeEqual(A,B);
};
export function guard(req,env=process.env){
 const keys=String(env.AEROLEADAI_API_KEYS||'').split(',').map(s=>s.trim()).filter(Boolean);
 if(!keys.length)return json(503,{error:'server_not_configured'});
 const origins=String(env.ALLOWED_ORIGINS||'').split(',').map(s=>s.trim()).filter(Boolean);
 if(origins.includes('*'))return json(503,{error:'wildcard_origin_not_allowed'});
 const origin=req.headers.get('origin');
 if(origin&&!origins.includes(origin))return json(403,{error:'origin_not_allowed'});
 const authorization=req.headers.get('authorization')||'';
 const token=authorization.startsWith('Bearer ')?authorization.slice(7).trim():'';
 if(!token||!keys.some(k=>eq(token,k)))return json(401,{error:'unauthorized'},{'www-authenticate':'Bearer'});
 return null;
}
