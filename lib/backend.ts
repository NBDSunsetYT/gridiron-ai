export type Backend='sqlite'|'supabase';
export function cloudOnlyDeployment(){return ['1','true'].includes(process.env.GRIDIRON_CLOUD_ONLY??'');}
export function selectedBackend(cookie?:string|null,configured=process.env.DATA_BACKEND):Backend{
 if(cloudOnlyDeployment())return 'supabase';
 if(cookie==='sqlite'||cookie==='supabase')return cookie;
 return configured==='supabase'?'supabase':'sqlite';
}
