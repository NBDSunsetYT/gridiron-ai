import { beforeAll, describe, expect, it } from 'vitest';
import { randomUUID } from 'node:crypto';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

process.env.APP_ORIGIN = 'http://localhost:3000';
process.env.DATA_DIR = mkdtempSync(join(tmpdir(), 'gridiron-auth-tests-'));
let auth: typeof import('../lib/auth');
let getDb: typeof import('../lib/db')['getDb'];
beforeAll(async () => {
  ({ getDb } = await import('../lib/db'));
  auth = await import('../lib/auth');
});
function createUser() {
  const id = randomUUID();
  const email = `${id}@example.test`;
  getDb().prepare('INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)')
    .run(id, email, 'unused-test-hash', new Date().toISOString());
  return { id, email };
}
function request(headers: Record<string, string> = {}) {
  return new Request('http://localhost:3000/api/account', { method: 'POST', headers: { 'content-type': 'application/json', origin: 'http://localhost:3000', ...headers } });
}

describe('Password and session security', () => {
  it('salts each password hash and verifies only the correct password', async () => {
    const hash = await auth.hashPassword('Correct horse battery staple!');
    const second = await auth.hashPassword('Correct horse battery staple!');
    expect(hash).not.toBe(second);
    expect(hash).not.toContain('Correct horse');
    expect(await auth.verifyPassword('Correct horse battery staple!', hash)).toBe(true);
    expect(await auth.verifyPassword('incorrect password', hash)).toBe(false);
    expect(await auth.verifyPassword('anything', 'malformed')).toBe(false);
  });
  it('stores only the digest of a session token and resolves the correct owner', async () => {
    const user = createUser();
    const token = auth.newSession(user.id);
    const session = getDb().prepare('SELECT token_hash,user_id FROM sessions WHERE user_id=?').get(user.id) as { token_hash: string; user_id: string };
    expect(session.token_hash).toBe(auth.digest(token));
    expect(session.token_hash).not.toBe(token);
    expect(await auth.getUser(request({ cookie: `${auth.SESSION_COOKIE}=${token}` }))).toEqual(user);
    expect(await auth.getUser(request({ cookie: `${auth.SESSION_COOKIE}=invalid` }))).toBeNull();
    expect(await auth.getUser(request())).toBeNull();
  });
  it('rejects expired sessions and unauthenticated protected access', async () => {
    const user = createUser(); const token = auth.newSession(user.id);
    getDb().prepare('UPDATE sessions SET expires_at=? WHERE token_hash=?').run('2000-01-01T00:00:00.000Z', auth.digest(token));
    expect(await auth.getUser(request({ cookie: `${auth.SESSION_COOKIE}=${token}` }))).toBeNull();
    await expect(auth.requireUser(request())).rejects.toMatchObject({ status: 401 });
  });
  it('sets HTTP-only, same-site cookies and Secure on HTTPS', () => {
    const cookie = auth.sessionCookie('abc', new Request('https://gridiron.example/api/auth'));
    expect(cookie).toContain('HttpOnly');
    expect(cookie).toContain('SameSite=Lax');
    expect(cookie).toContain('; Secure');
    expect(auth.sessionCookie('', new Request('https://gridiron.example/api/auth'))).toContain('Max-Age=0');
  });
});

describe('Request boundaries', () => {
  it('accepts the browser Host in local Next requests while pinning a configured deployment origin', () => {
    const previous=process.env.APP_URL,alias=process.env.APP_ORIGIN;
    delete process.env.APP_URL;delete process.env.APP_ORIGIN;
    try{
      const local=new Request('http://localhost:3000/api/auth',{method:'POST',headers:{host:'127.0.0.1:3000',origin:'http://127.0.0.1:3000','content-type':'application/json'}});
      expect(()=>auth.guardMutation(local)).not.toThrow();
      process.env.APP_URL='https://gridiron.example';
      expect(()=>auth.guardMutation(local)).toThrow();
      expect(auth.requestOrigin(local)).toBe('https://gridiron.example');
    }finally{if(previous===undefined)delete process.env.APP_URL;else process.env.APP_URL=previous;if(alias===undefined)delete process.env.APP_ORIGIN;else process.env.APP_ORIGIN=alias;}
  });
  it('rejects cross-origin mutations while permitting same-origin JSON', () => {
    expect(() => auth.guardMutation(request())).not.toThrow();
    expect(() => auth.guardMutation(request({ origin: 'https://attacker.example' }))).toThrow();
    try { auth.guardMutation(request({ origin: 'https://attacker.example' })); } catch (error) {
      expect(error).toMatchObject({ status: 403 });
    }
  });
  it('rejects unsupported content types and oversized declared payloads', () => {
    expect(() => auth.guardMutation(request({ 'content-type': 'text/plain' }))).toThrow();
    expect(() => auth.guardMutation(request({ 'content-length': '1000001' }))).toThrow();
  });
  it('returns a rate-limit error after the allowed request count', () => {
    const key = `test-${randomUUID()}`;
    auth.rateLimit(key, 2);
    auth.rateLimit(key, 2);
    expect(() => auth.rateLimit(key, 2)).toThrow();
    try { auth.rateLimit(key, 2); } catch (error) {
      expect(error).toMatchObject({ status: 429 });
    }
  });
  it('returns structured status codes without leaking internal errors', async () => {
    const validation = auth.errorResponse(new auth.ApiError('Invalid amount.', 400));
    expect(validation.status).toBe(400);
    expect(await validation.json()).toEqual({ error: 'Invalid amount.' });
    const invalidJson = auth.errorResponse(new SyntaxError('Unexpected token'));
    expect(invalidJson.status).toBe(400);
    expect(await invalidJson.json()).toEqual({ error: 'Invalid JSON request.' });
  });
});
