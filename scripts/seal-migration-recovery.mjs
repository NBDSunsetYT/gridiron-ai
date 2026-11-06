/** Operator logical row export, accepted through stdin with terminal echo off.
 * No credentials or row payloads are logged. Not an Auth/Storage/PITR backup.
 */
import {createInterface} from 'node:readline';
import {randomBytes,createCipheriv,createDecipheriv,createHash} from 'node:crypto';
import {gzipSync,gunzipSync} from 'node:zlib';
import {mkdirSync,writeFileSync,readFileSync,chmodSync} from 'node:fs';
import {resolve,join} from 'node:path';
const directory=resolve(process.env.RECOVERY_DIRECTORY||'artifacts/render-migration-v24/private-recovery');
mkdirSync(directory,{recursive:true,mode:0o700});chmodSync(directory,0o700);
const lines=createInterface({input:process.stdin});
console.log('Recovery receiver ready; supply one JSON export, never a shell command.');
lines.once('line',line=>{
 try{
  const value=JSON.parse(line);if(!value.tables||value.project!=='qdtdjbapdipopncklsdb')throw Error('Unexpected recovery scope');
  const raw=Buffer.from(JSON.stringify(value)),compressed=gzipSync(raw),key=randomBytes(32),iv=randomBytes(12),cipher=createCipheriv('aes-256-gcm',key,iv),ciphertext=Buffer.concat([cipher.update(compressed),cipher.final()]);
  const envelope={format:'gridiron-logical-recovery-v1',algorithm:'aes-256-gcm+gzip',iv:iv.toString('base64'),tag:cipher.getAuthTag().toString('base64'),ciphertext:ciphertext.toString('base64'),plaintextSha256:createHash('sha256').update(raw).digest('hex')};
  writeFileSync(join(directory,'recovery.encrypted.json'),JSON.stringify(envelope),{mode:0o600,flag:'wx'});
  writeFileSync(join(directory,'recovery.key'),key.toString('base64'),{mode:0o600,flag:'wx'});
  const reopened=JSON.parse(readFileSync(join(directory,'recovery.encrypted.json'),'utf8')),decipher=createDecipheriv('aes-256-gcm',Buffer.from(readFileSync(join(directory,'recovery.key'),'utf8'),'base64'),Buffer.from(reopened.iv,'base64'));decipher.setAuthTag(Buffer.from(reopened.tag,'base64'));
  const restored=gunzipSync(Buffer.concat([decipher.update(Buffer.from(reopened.ciphertext,'base64')),decipher.final()]));
  if(!raw.equals(restored))throw Error('Recovery round-trip mismatch');
  const receipt={checkedAt:new Date().toISOString(),project:value.project,scope:'Selected private public-schema row tables; excludes Auth secrets, external storage and shared datasets',rows:Object.fromEntries(Object.entries(value.tables).map(([table,rows])=>[table,rows.length])),bytes:raw.length,compressedBytes:compressed.length,sha256:envelope.plaintextSha256,decryptionVerified:true,fullDatabaseRestoreVerified:false,offHostBackupVerified:false};
  writeFileSync(join(directory,'receipt.json'),JSON.stringify(receipt,null,2),{mode:0o600});console.log(JSON.stringify(receipt));
 }catch(error){console.error('Recovery export failed; no source records were changed.',{name:error?.name,code:error?.code});process.exitCode=1;}
 finally{lines.close();}
});
