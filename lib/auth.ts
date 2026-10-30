import { randomBytes, createHash, scrypt as scryptCallback, timingSafeEqual } from 'node:crypto';
import { promisify } from 'node:util';
import { getDb } from './db';
const scrypt = promisify(scryptCallback);
export class ApiError extends Error { constructor(message: string, public status = 400) { super(message); } }
export const SESSION_COOKIE = 'gridiron_session';
export type User = { id: string; email: string };
export const digest = (value: string) => createHash('sha256').update(value).digest('hex');
export async function hashPassword(password: string) {
  const salt = randomBytes(16).toString('hex');
  const hash = await scrypt(password, salt, 64) as Buffer;
  return `${salt}:${hash.toString('hex')}`;
}
export async function verifyPassword(password: string, serialized: string) {
  const [salt, hash] = serialized.split(':');
  if (!salt || !hash) return false;
  const expected = Buffer.from(hash, 'hex'); const actual = await scrypt(password, salt, 64) as Buffer;
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}
export function rateLimit(key: string, limit = 60, windowMs = 60_000) {
  const db = getDb(); const now = Date.now();
  const value = db.prepare('SELECT count,reset_at FROM rate_limits WHERE key=?').get(key) as {count:number;reset_at:number}|undefined;
  if (value && value.reset_at > now && value.count >= limit) throw new ApiError('Too many requests. Please try again later.',429);
  db.prepare('INSERT INTO rate_limits(key,count,reset_at) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN reset_at<=? THEN 1 ELSE count+1 END,reset_at=CASE WHEN reset_at<=? THEN excluded.reset_at ELSE reset_at END').run(key,now+windowMs,now,now);
  db.prepare('DELETE FROM rate_limits WHERE reset_at < ?').run(now-86_400_000);
}
export function guardMutation(request: Request) {
  const origin = request.headers.get('origin');
  const expected = requestOrigin(request);
  if (origin && origin !== expected) throw new ApiError('Cross-origin requests are not allowed.',403);
  const contentType = request.headers.get('content-type') || '';
  if (!/^application\/json(?:;|$)/i.test(contentType)) throw new ApiError('Use application/json.',415);
  const size = Number(request.headers.get('content-length') || 0);
  if (size > 1_000_000) throw new ApiError('Request is too large.',413);
}
/** Next's internal request URL can use localhost even when the browser uses 127.0.0.1.
 * Production deployments pin APP_URL; local requests use the actual Host header.
 * Forwarded host headers are deliberately not used as an authorization source. */
export function requestOrigin(request:Request){
  const configured=process.env.APP_ORIGIN||process.env.APP_URL;
  if(configured)return new URL(configured).origin;
  const url=new URL(request.url),host=request.headers.get('host');
  return host?new URL(`${url.protocol}//${host}`).origin:url.origin;
}
export async function readJsonObject(request:Request):Promise<Record<string,any>> {
  const reader=request.body?.getReader();if(!reader)throw new ApiError('A JSON object is required.');
  const chunks:Uint8Array[]=[];let bytes=0;
  while(true){const chunk=await reader.read();if(chunk.done)break;bytes+=chunk.value.byteLength;if(bytes>1_000_000){await reader.cancel();throw new ApiError('Request is too large.',413);}chunks.push(chunk.value);}
  const data=JSON.parse(Buffer.concat(chunks).toString('utf8'));
  if(!data||typeof data!=='object'||Array.isArray(data))throw new ApiError('A JSON object is required.');
  return data;
}
export async function getUser(request?: Request): Promise<User|null> {
  let cookie: string | undefined;
  if (request) cookie = request.headers.get('cookie') || undefined;
  else { const { headers } = await import('next/headers'); cookie = (await headers()).get('cookie') || undefined; }
  const token = cookie?.split(';').map(s=>s.trim()).find(s=>s.startsWith(SESSION_COOKIE+'='))?.slice(SESSION_COOKIE.length+1);
  if (!token || !/^[a-f0-9]{64}$/.test(token)) return null;
  const row = getDb().prepare('SELECT users.id,users.email FROM sessions JOIN users ON users.id=sessions.user_id WHERE token_hash=? AND expires_at>?').get(digest(token),new Date().toISOString()) as User|undefined;
  return row || null;
}
export async function requireUser(request?: Request): Promise<User> {
  const user = await getUser(request); if (!user) throw new ApiError('Sign in to access your private records.',401); return user;
}
export function newSession(userId:string) {
  const token = randomBytes(32).toString('hex'); const expires = new Date(Date.now()+30*86_400_000).toISOString();
  getDb().prepare('DELETE FROM sessions WHERE expires_at<?').run(new Date().toISOString());
  getDb().prepare('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)').run(digest(token),userId,expires);
  return token;
}
export function sessionCookie(token:string, request:Request) {
  const secure = new URL(request.url).protocol === 'https:' || (process.env.APP_ORIGIN || process.env.APP_URL)?.startsWith('https:');
  return `${SESSION_COOKIE}=${token}; HttpOnly; Path=/; SameSite=Lax; Max-Age=${token ? 2592000 : 0}${secure ? '; Secure' : ''}`;
}
export function errorResponse(error:unknown) {
  if (error instanceof ApiError) return Response.json({error:error.message},{status:error.status});
  if (error instanceof SyntaxError) return Response.json({error:'Invalid JSON request.'},{status:400});
  if (error instanceof Error && error.message.includes('UNIQUE constraint')) return Response.json({error:'A record with this reference already exists.'},{status:409});
  console.error('API operation failed.',{name:error instanceof Error ? error.name : 'UnknownError'});
  return Response.json({error:'The operation could not be completed. Please try again.'},{status:500});
}
