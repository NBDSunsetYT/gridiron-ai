// @ts-nocheck -- Supabase Deno entrypoint; verified separately from Next.js.
import {createClient} from 'npm:@supabase/supabase-js@2.118.0';
const BUCKET='gridiron-shared-research-v1',MAX_COMPRESSED=2_000_000,MAX_RAW=20_000_000;
const json=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
const sha=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(b=>b.toString(16).padStart(2,'0')).join('');
const forbidden=/^(?:user_id|userId|email|password|authorization|cookie|api_?key|access_token|accessToken|refresh_token|refreshToken|service_role_key|serviceRoleKey|token|bankroll|deposits|withdrawals|cashBalanceCents)$/i;
function publicOnly(value,depth=0){if(depth>45)return false;if(!value||typeof value!=='object')return true;if(Array.isArray(value))return value.every(v=>publicOnly(v,depth+1));return Object.entries(value).every(([key,v])=>!forbidden.test(key)&&publicOnly(v,depth+1));}
async function bounded(stream,limit){const reader=stream.getReader(),parts=[];let size=0;try{for(;;){const {value,done}=await reader.read();if(done)break;size+=value.byteLength;if(size>limit){await reader.cancel();throw Error('size');}parts.push(value);}}finally{reader.releaseLock();}const result=new Uint8Array(size);let at=0;for(const p of parts){result.set(p,at);at+=p.byteLength;}return result;}
Deno.serve(async req=>{
 try{
  // This function authenticates the existing server capability itself. No app user's JWT is elevated.
  const token=req.headers.get('x-gridiron-server-token');if(!token||token.length<40||token.length>512)return json({code:'authentication_failure'},401);
  const url=Deno.env.get('SUPABASE_URL'),keys=JSON.parse(Deno.env.get('SUPABASE_SECRET_KEYS')||'{}'),key=keys.default||Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');if(!url||!key)return json({code:'backend_configuration'},503);
  const client=createClient(url,key,{auth:{persistSession:false,autoRefreshToken:false}}),auth=await client.rpc('gridiron_shared_storage_authorized',{token});if(auth.error)return json({code:'authorization_check_unavailable'},503);if(auth.data!==true)return json({code:'authentication_failure'},401);
  const query=new URL(req.url).searchParams,id=query.get('id');if(!id||!/^[a-f0-9]{64}$/.test(id))return json({code:'invalid_object_identity'},400);const path='sha256/'+id+'.json.gz';
  if(req.method==='GET'){const result=await client.storage.from(BUCKET).download(path);if(result.error)return json({code:'object_unavailable'},result.error.statusCode==='404'?404:503);const bytes=new Uint8Array(await result.data.arrayBuffer());if(bytes.length>MAX_COMPRESSED||await sha(bytes)!==id)return json({code:'object_integrity_failure'},502);return new Response(bytes,{headers:{'Content-Type':'application/octet-stream','Cache-Control':'no-store','X-Content-SHA256':id}});}
  if(req.method!=='PUT')return json({code:'unsupported_method'},405);
  if(Number(req.headers.get('content-length')??0)>MAX_COMPRESSED)return json({code:'object_too_large'},413);
  const bytes=await bounded(req.body,MAX_COMPRESSED);if(await sha(bytes)!==id)return json({code:'object_integrity_failure'},422);
  const raw=await bounded(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip')),MAX_RAW),value=JSON.parse(new TextDecoder().decode(raw));if(!publicOnly(value))return json({code:'private_data_not_allowed'},422);
  const bucket=await client.storage.getBucket(BUCKET);if(bucket.error){const created=await client.storage.createBucket(BUCKET,{public:false,fileSizeLimit:MAX_COMPRESSED,allowedMimeTypes:['application/gzip']});if(created.error&&!/already exists/i.test(created.error.message))return json({code:'bucket_unavailable'},503);}else if(bucket.data.public)return json({code:'bucket_security_mismatch'},503);
  const saved=await client.storage.from(BUCKET).upload(path,bytes,{contentType:'application/gzip',upsert:false,cacheControl:'31536000'});
  if(saved.error){const existing=await client.storage.from(BUCKET).download(path);if(existing.error||await sha(new Uint8Array(await existing.data.arrayBuffer()))!==id)return json({code:'object_write_unavailable'},503);}
  return json({saved:true,id,bytes:bytes.length,rawBytes:raw.length,rawSha256:await sha(raw)});
 }catch{return json({code:'temporary_service_failure'},503);}
});
