import validation from '@/docs/reports/v15-validation.json';
import diagnostic from '@/docs/reports/v15-original-run-diagnostic.json';
export const runtime='nodejs';
export async function GET(request:Request){const view=new URL(request.url).searchParams.get('view');if(view&&view!=='diagnostic')return Response.json({error:'Unsupported validation view.'},{status:400,headers:{'Cache-Control':'no-store'}});return Response.json(view==='diagnostic'?diagnostic:validation,{headers:{'Cache-Control':'public, max-age=0, s-maxage=300','X-Content-Type-Options':'nosniff'}});}
