import {describe,it,expect} from 'vitest';
import {mkdtempSync,writeFileSync,readFileSync,statSync,existsSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {spawnSync} from 'node:child_process';
import {scryptSync,createCipheriv} from 'node:crypto';
import {gzipSync} from 'node:zlib';
import {decryptBackup,encryptBackup,BACKUP_EXPANDED_LIMIT,type EncryptedBackup} from '../lib/backups';
const password='SYNTHETIC-LEGACY-RECOVERY-PASSWORD';
// Fixed original AES-GCM JSON envelope produced independently of encryptBackup.
const legacy:EncryptedBackup={format:'gridiron-encrypted-backup-v1',cipher:'aes-256-gcm',kdf:'scrypt',salt:'BwcHBwcHBwcHBwcHBwcHBw==',iv:'CQkJCQkJCQkJCQkJ',tag:'x0tvRZz7J9FHQtnY2OaJaA==',ciphertext:'NC94tSv9xhY6IVQQj55+pWMRaq4RAJpRU1BTfbfuUqY/ARYeDhkEapcsjXw6homRlh6l+GJIZk01r1T8NY/YgGgHTIZM9VcRdEQOJanbRNw5L5f43oNLEt70S0yKttSRivTl1Q=='};
const legacyPayload={version:2,ledger:{summary:{cashBalanceCents:10001}},note:'SYNTHETIC original v1 fixture'};
function malformedExpansion(){
 const salt=Buffer.alloc(16,3),iv=Buffer.alloc(12,4),cipher=createCipheriv('aes-256-gcm',scryptSync(password,salt,32),iv),uncompressedBytes=32;
 cipher.setAAD(Buffer.from(JSON.stringify(['gridiron-encrypted-backup-v2','gzip',uncompressedBytes])));
 const bytes=gzipSync(Buffer.from(JSON.stringify({evidence:'SYNTHETIC'.repeat(100000)}))),ciphertext=Buffer.concat([cipher.update(bytes),cipher.final()]);
 return{format:'gridiron-encrypted-backup-v2' as const,cipher:'aes-256-gcm' as const,kdf:'scrypt' as const,compression:'gzip' as const,uncompressedBytes,salt:salt.toString('base64'),iv:iv.toString('base64'),tag:cipher.getAuthTag().toString('base64'),ciphertext:ciphertext.toString('base64')};
}
describe('Bounded lossless compressed evidence archives',()=>{
 it('continues to decrypt fixed original v1 financial archives',async()=>{expect(await decryptBackup(legacy,password)).toEqual(legacyPayload);});
 it('round-trips a complete evidence archive beyond the former 60 MB bound',async()=>{
  const evidence='SYNTHETIC-CORRELATED-HISTORICAL-EVIDENCE\n'.repeat(1600000),payload={version:2,ledger:{summary:{cashBalanceCents:52500,realizedPlCents:7500}},research:{completeEvidence:evidence,inputProof:{version:1,algorithm:'hmac-sha256',mac:'a'.repeat(64)}}};
  expect(Buffer.byteLength(JSON.stringify(payload))).toBeGreaterThan(60_000_000);
  const encrypted=await encryptBackup(payload,password);expect(encrypted.format).toBe('gridiron-encrypted-backup-v2');expect(encrypted.ciphertext.length).toBeLessThan(1_000_000);expect(await decryptBackup(encrypted,password)).toEqual(payload);
 },20000);
 it('authenticates compression metadata and refuses format downgrade',async()=>{
  const encrypted=await encryptBackup({evidence:'SYNTHETIC'.repeat(130000)},password);if(encrypted.format!=='gridiron-encrypted-backup-v2')throw Error('Expected compression');
  await expect(decryptBackup({...encrypted,uncompressedBytes:encrypted.uncompressedBytes-1},password)).rejects.toThrow(/authenticat|integrity/i);
  await expect(decryptBackup({...encrypted,format:'gridiron-encrypted-backup-v1'},password)).rejects.toThrow(/authenticat|integrity/i);
  await expect(decryptBackup({...encrypted,compression:'unknown'} as unknown as EncryptedBackup,password)).rejects.toThrow(/encoding/i);
 });
 it('rejects an authenticated compression bomb and oversized declared expansion before accepting any partial archive',async()=>{
  const bomb=malformedExpansion();await expect(decryptBackup(bomb,password)).rejects.toThrow(/authenticat|integrity/i);
  await expect(decryptBackup({...bomb,uncompressedBytes:BACKUP_EXPANDED_LIMIT+1},password)).rejects.toThrow(/size/i);
  await expect(decryptBackup({...bomb,uncompressedBytes:-1},password)).rejects.toThrow(/size/i);
 });
 it('recovers both envelope versions with the standalone CLI using private output and stdin-only passphrases',async()=>{
  const directory=mkdtempSync(join(tmpdir(),'gridiron-backup-cli-test-'));
  try{
   const payload={...legacyPayload,research:{completeEvidence:'SYNTHETIC'.repeat(130000)}};
   const variants=[legacy,await encryptBackup(payload,password)];
   for(let i=0;i<variants.length;i++){
    const input=join(directory,`encrypted-${i}.json`),output=join(directory,`recovered-${i}.json`);writeFileSync(input,JSON.stringify(variants[i]),{mode:0o600});
    const result=spawnSync(process.execPath,[resolve('scripts/decrypt-backup.mjs'),input,output],{input:password+'\n',encoding:'utf8'});
    expect(result.status).toBe(0);expect(JSON.parse(readFileSync(output,'utf8'))).toEqual(i===0?legacyPayload:payload);expect(statSync(output).mode&0o777).toBe(0o600);
    const previous=readFileSync(output,'utf8'),repeated=spawnSync(process.execPath,[resolve('scripts/decrypt-backup.mjs'),input,output],{input:password+'\n',encoding:'utf8'});expect(repeated.status).toBe(1);expect(readFileSync(output,'utf8')).toBe(previous);
   }
   const denied=join(directory,'wrong-password.json'),failed=spawnSync(process.execPath,[resolve('scripts/decrypt-backup.mjs'),join(directory,'encrypted-0.json'),denied],{input:'SYNTHETIC-WRONG-RECOVERY-PASSWORD\n',encoding:'utf8'});expect(failed.status).toBe(1);expect(existsSync(denied)).toBe(false);
  }finally{rmSync(directory,{recursive:true,force:true});}
 },10000);
});
