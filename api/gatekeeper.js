// GateKeeper LuckyG AI endpoint. Server-side only; configure ANTHROPIC_API_KEY in Vercel.
// Never put keys or the service-role key in the browser or repository.
export default async function handler(req,res){
 res.setHeader('Cache-Control','no-store');
 if(req.method!=='POST'){res.setHeader('Allow','POST');return res.status(405).json({error:'Method not allowed'})}
 const token=process.env.ANTHROPIC_API_KEY;
 if(!token)return res.status(503).json({error:'AI not configured. Use evidence-backed local answers.'});
 const question=String(req.body?.question||'').trim();
 const history=Array.isArray(req.body?.messages)?req.body.messages.slice(-12):[];
 if(!question||question.length>2000)return res.status(400).json({error:'Question must be 1–2000 characters'});
 const messages=history.filter(x=>['user','assistant'].includes(x?.role)&&typeof x.content==='string')
  .map(x=>({role:x.role,content:x.content.slice(0,2000)})).slice(-12);
 if(messages.at(-1)?.role!=='user'||messages.at(-1)?.content!==question)messages.push({role:'user',content:question});
 const timeout=AbortSignal.timeout(18000);
 try{
 const response=await fetch('https://api.anthropic.com/v1/messages',{method:'POST',signal:timeout,headers:{
 'Content-Type':'application/json','x-api-key':token,'anthropic-version':'2023-06-01'
 },body:JSON.stringify({model:process.env.ANTHROPIC_MODEL||'claude-sonnet-4-5',max_tokens:600,
 system:'You are LuckyG GateKeeper inside AeroLeadAI. You may NOT claim to have live backend access. You are not given live database state, permit packets, or imagery. Do not invent property assessments, scores, alerts, permit counts, or financial valuations. A public GitHub CSV is an unverified parcel candidate list, not a completed investigation. If a user asks for a concrete live fact absent supplied verified context, clearly say it is unavailable and point to official records. Keep answers concise.',
 messages})});
 const data=await response.json().catch(()=>({}));
 if(!response.ok)return res.status(502).json({error:'AI provider unavailable ('+response.status+').'});
 return res.status(200).json({answer:(data.content||[]).filter(x=>x.type==='text').map(x=>x.text).join('\n')||'No response from provider'});
 }catch(e){return res.status(502).json({error:'AI provider request timed out or failed'})}
}
