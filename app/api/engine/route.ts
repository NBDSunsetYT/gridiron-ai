import calibration from '@/docs/reports/model-audit-v17-summary.json';
import validation from '@/docs/reports/v15-validation.json';
import diagnostic from '@/docs/reports/v15-original-run-diagnostic.json';
import iterations from '@/docs/reports/v16-iterative-learning.json';
import paired from '@/docs/reports/v16-paired-analysis.json';
import protocol from '@/docs/reports/v16-protocol.json';
export const runtime='nodejs';
export async function GET(request:Request){
 const view=new URL(request.url).searchParams.get('view');
 const reports={diagnostic,iterations,paired,protocol,calibration};
 if(view&&!Object.hasOwn(reports,view))return Response.json({error:'Unsupported validation view.'},{status:400,headers:{'Cache-Control':'no-store'}});
 return Response.json(view?reports[view as keyof typeof reports]:validation,{headers:{'Cache-Control':'public, max-age=0, s-maxage=300','CDN-Cache-Control':'public, s-maxage=300','Vercel-CDN-Cache-Control':'public, s-maxage=300','X-Content-Type-Options':'nosniff'}});
}
