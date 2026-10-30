import {randomBytes,scrypt as scryptCallback,createCipheriv,createDecipheriv} from 'node:crypto';
import {gzip as gzipCallback,gunzip as gunzipCallback} from 'node:zlib';
import {promisify} from 'node:util';
import {ApiError} from './auth';
const scrypt=promisify(scryptCallback),gzip=promisify(gzipCallback),gunzip=promisify(gunzipCallback);
/** Bounds apply before allocation/decompression. Large evidence archives are
 * compressed losslessly before encryption; historical v1 archives still open. */
export const BACKUP_EXPANDED_LIMIT=160_000_000;
export const BACKUP_CIPHERTEXT_LIMIT=100_000_000;
const COMPRESSION_THRESHOLD=1_000_000;
type BaseBackup={cipher:'aes-256-gcm';kdf:'scrypt';salt:string;iv:string;tag:string;ciphertext:string};
export type EncryptedBackup=(BaseBackup&{format:'gridiron-encrypted-backup-v1'})|(BaseBackup&{format:'gridiron-encrypted-backup-v2';compression:'gzip';uncompressedBytes:number});
function validatePassword(password:unknown):asserts password is string{if(typeof password!=='string'||password.length<12||password.length>128)throw new ApiError('Backup password must contain 12–128 characters.');}
function metadata(bytes:number){return Buffer.from(JSON.stringify(['gridiron-encrypted-backup-v2','gzip',bytes]),'utf8');}
export async function encryptBackup(payload:unknown,password:string):Promise<EncryptedBackup>{
 validatePassword(password);const raw=Buffer.from(JSON.stringify(payload),'utf8');
 if(raw.length>BACKUP_EXPANDED_LIMIT)throw new ApiError('The complete expanded backup exceeds the 160 MB recovery bound. No partial archive was returned; use a consistent project backup.',413);
 const compressed=raw.length>=COMPRESSION_THRESHOLD,content=compressed?await gzip(raw,{level:6}):raw;
 if(Math.ceil(content.length/3)*4>BACKUP_CIPHERTEXT_LIMIT)throw new ApiError('The encrypted archive exceeds the supported 100 MB encoded transfer bound. No partial archive was returned.',413);
 const salt=randomBytes(16),iv=randomBytes(12),key=await scrypt(password,salt,32) as Buffer;
 try{
  const cipher=createCipheriv('aes-256-gcm',key,iv);if(compressed)cipher.setAAD(metadata(raw.length));
  const encrypted=Buffer.concat([cipher.update(content),cipher.final()]);
  const common={cipher:'aes-256-gcm' as const,kdf:'scrypt' as const,salt:salt.toString('base64'),iv:iv.toString('base64'),tag:cipher.getAuthTag().toString('base64'),ciphertext:encrypted.toString('base64')};
  return compressed?{...common,format:'gridiron-encrypted-backup-v2',compression:'gzip',uncompressedBytes:raw.length}:{...common,format:'gridiron-encrypted-backup-v1'};
 }finally{key.fill(0);}
}
export async function decryptBackup(backup:EncryptedBackup,password:string):Promise<unknown>{
 validatePassword(password);
 if(!['gridiron-encrypted-backup-v1','gridiron-encrypted-backup-v2'].includes(backup?.format)||backup.cipher!=='aes-256-gcm'||backup.kdf!=='scrypt')throw new ApiError('Unsupported encrypted backup format.');
 const compressed=backup.format==='gridiron-encrypted-backup-v2';
 if(compressed&&(backup.compression!=='gzip'||!Number.isSafeInteger(backup.uncompressedBytes)||backup.uncompressedBytes<1||backup.uncompressedBytes>BACKUP_EXPANDED_LIMIT))throw new ApiError('Invalid compressed backup size or encoding.');
 if(![backup.salt,backup.iv,backup.tag,backup.ciphertext].every(value=>typeof value==='string')||backup.salt.length>100||backup.iv.length>100||backup.tag.length>100||backup.ciphertext.length>BACKUP_CIPHERTEXT_LIMIT)throw new ApiError('Invalid encrypted backup.');
 const salt=Buffer.from(backup.salt,'base64'),iv=Buffer.from(backup.iv,'base64'),tag=Buffer.from(backup.tag,'base64');
 if(salt.length!==16||iv.length!==12||tag.length!==16)throw new ApiError('Invalid encrypted backup.');
 const key=await scrypt(password,salt,32) as Buffer;
 try{
  const decipher=createDecipheriv('aes-256-gcm',key,iv);if(compressed)decipher.setAAD(metadata(backup.uncompressedBytes));decipher.setAuthTag(tag);
  let raw=Buffer.concat([decipher.update(Buffer.from(backup.ciphertext,'base64')),decipher.final()]);
  if(compressed){raw=await gunzip(raw,{maxOutputLength:Math.min(BACKUP_EXPANDED_LIMIT,backup.uncompressedBytes+1)});if(raw.length!==backup.uncompressedBytes)throw Error('size');}
  if(raw.length>BACKUP_EXPANDED_LIMIT)throw Error('size');
  return JSON.parse(raw.toString('utf8'));
 }catch{throw new ApiError('Backup could not be authenticated. Check the password and file integrity.');}finally{key.fill(0);}
}
