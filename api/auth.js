import {createHmac,timingSafeEqual} from 'node:crypto';
const cookieName='aero_session',maxAge=60*60*12;
function sig(value){return createHmac('sha256',process.env.AERO_SESSION_SECRET||'').update(value).digest('base64url')}
function equal(a,b){const A=Buffer.from(String(a||'')),B=Buffer.from(String(b||''));return A.length===B.length&&timingSafeEqual(A,B)}
export function authorized(req){const raw=(req.headers.cookie||'').split(';').map(x=>x.trim()).find(x=>x.startsWith(cookieName+'='));if(!raw)return false;const [exp,mac]=(raw.slice(cookieName.length+1)).split('.');if(!/^\d+$/.test(exp)||Date.now()>Number(exp)||!mac)return false;return equal(mac,sig(exp))}
export default async function handler(req,res){
 res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');
 if(!process.env.AERO_ACCESS_PASSCODE||!process.env.AERO_SESSION_SECRET)return res.status(503).json({authorized:false,error:'Access control not configured'});
 if(req.method==='GET')return res.status(200).json({authorized:authorized(req)});
 if(req.method==='DELETE'){res.setHeader('Set-Cookie',cookieName+'=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0');return res.status(200).json({authorized:false})}
 if(req.method!=='POST')return res.status(405).json({error:'Method not allowed'});
 const candidate=typeof req.body?.passcode==='string'?req.body.passcode:'';
 if(candidate.length>128||!equal(candidate,process.env.AERO_ACCESS_PASSCODE))return res.status(401).json({authorized:false,error:'Incorrect passcode'});
 const exp=String(Date.now()+maxAge*1000);
 res.setHeader('Set-Cookie',cookieName+'='+exp+'.'+sig(exp)+'; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age='+maxAge);
 return res.status(200).json({authorized:true});
}
