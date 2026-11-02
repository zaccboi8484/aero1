// Runtime deployment fingerprint, deliberately excludes secrets.
export default function handler(req,res) {
 res.setHeader('Cache-Control','no-store');
 if(req.method!=='GET') return res.status(405).json({error:'method_not_allowed'});
 return res.status(200).json({
  commit:process.env.VERCEL_GIT_COMMIT_SHA||null,
  branch:process.env.VERCEL_GIT_COMMIT_REF||null,
  environment:process.env.VERCEL_ENV||null,
  source:'vercel-runtime',
  deployed:Boolean(process.env.VERCEL_GIT_COMMIT_SHA)
 });
}
