import {describe,expect,it} from 'vitest';
import {decryptDeviceToken,encryptDeviceToken,validateDeviceToken} from '../lib/native/device-tokens.server';
describe('Private native device registrations',()=>{
 const token='a1'.repeat(32),secret='SYNTHETIC-ENCRYPTION-KEY-DO-NOT-USE-2026';
 it('accepts only real-shaped APNs input with an explicit environment',()=>{expect(validateDeviceToken({platform:'ios',token,environment:'development'})).toEqual({platform:'ios',token,environment:'development'});for(const value of [{platform:'web',token,environment:'development'},{platform:'ios',token:'not-an-APNs-token',environment:'production'},{platform:'ios',token,environment:'unknown'}])expect(()=>validateDeviceToken(value)).toThrow();});
 it('encrypts token values at rest and verifies ciphertext integrity',()=>{const a=encryptDeviceToken(token,secret),b=encryptDeviceToken(token,secret);expect(JSON.stringify(a)).not.toContain(token);expect(a.ciphertext).not.toEqual(b.ciphertext);expect(a.iv).not.toEqual(b.iv);expect(a.fingerprint).toEqual(b.fingerprint);expect(decryptDeviceToken(a,secret)).toEqual(token);expect(()=>decryptDeviceToken(a,secret+'wrong')).toThrow();const bytes=Buffer.from(a.ciphertext,'base64');bytes[0]^=1;expect(()=>decryptDeviceToken({...a,ciphertext:bytes.toString('base64')},secret)).toThrow();});
 it('refuses unconfigured server-side encryption rather than storing plaintext',()=>{expect(()=>encryptDeviceToken(token,'')).toThrow(/DEVICE_TOKEN_ENCRYPTION_KEY/);});
});
