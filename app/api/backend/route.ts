import {guardMutation,readJsonObject,errorResponse,ApiError} from '@/lib/auth';
import {selectedBackend,cloudOnlyDeployment} from '@/lib/backend';
export const dynamic='force-dynamic';
let observed:{at:number;reachable:boolean}|null=null;
export async function GET(request:Request){
 const cookie=request.headers.get('cookie')?.split(';').map(s=>s.trim()).find(s=>s.startsWith('gridiron_backend='))?.slice('gridiron_backend='.length);
 const configured=Boolean(process.env.SUPABASE_URL&&process.env.SUPABASE_PUBLISHABLE_KEY);
 if(configured&&(!observed||Date.now()-observed.at>30000)){
  try{const r=await fetch(new URL('/auth/v1/health',process.env.SUPABASE_URL),{headers:{apikey:process.env.SUPABASE_PUBLISHABLE_KEY!},signal:AbortSignal.timeout(5000),cache:'no-store'});observed={at:Date.now(),reachable:r.ok};}catch{observed={at:Date.now(),reachable:false};}
 }
 return Response.json({backend:selectedBackend(cookie),availableBackends:cloudOnlyDeployment()?['supabase']:['sqlite','supabase'],cloudOnly:cloudOnlyDeployment(),cloud:{configured,reachable:configured?observed?.reachable??null:null,checkedAt:observed?new Date(observed.at).toISOString():null},legacyPreserved:true,policy:cloudOnlyDeployment()?'This deployment stores account records in Supabase. The original SQLite workspace is preserved on its original server; use an owned encrypted backup to migrate.':'Switching changes the selected authenticated workspace. Existing SQLite records are retained; migration requires an explicit owned backup import.'},{headers:{'Cache-Control':'private,no-store'}});
}
export async function POST(request:Request){try{
 guardMutation(request);const body=await readJsonObject(request);
 if(!['sqlite','supabase'].includes(body.backend))throw new ApiError('Choose sqlite or supabase.');
 if(body.backend==='sqlite'&&cloudOnlyDeployment())throw new ApiError('This hosted deployment uses persistent Supabase storage. The original SQLite workspace was preserved on its original server.',409);
 if(body.backend==='supabase'&&(!process.env.SUPABASE_URL||!process.env.SUPABASE_PUBLISHABLE_KEY))throw new ApiError('The Supabase server connection has not been configured.',503);
 const secure=new URL(request.url).protocol==='https:'||(process.env.APP_URL||process.env.APP_ORIGIN)?.startsWith('https:');
 return Response.json({backend:body.backend,preserved:true},{headers:{'Set-Cookie':`gridiron_backend=${body.backend}; HttpOnly; Path=/; SameSite=Lax; Max-Age=31536000${secure?'; Secure':''}`,'Cache-Control':'no-store'}});
 }catch(e){return errorResponse(e);}}
