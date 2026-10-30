import {randomBytes,scrypt as scryptCallback,createCipheriv,createDecipheriv} from 'node:crypto';
import {promisify} from 'node:util';
import {ApiError} from './auth';
const scrypt=promisify(scryptCallback);
export type EncryptedBackup={format:'gridiron-encrypted-backup-v1';cipher:'aes-256-gcm';kdf:'scrypt';salt:string;iv:string;tag:string;ciphertext:string};
function validatePassword(password:unknown):asserts password is string{if(typeof password!=='string'||password.length<12||password.length>128)throw new ApiError('Backup password must contain 12–128 characters.');}
export async function encryptBackup(payload:unknown,password:string):Promise<EncryptedBackup>{
  validatePassword(password);const salt=randomBytes(16),iv=randomBytes(12),key=await scrypt(password,salt,32) as Buffer;
  try{const cipher=createCipheriv('aes-256-gcm',key,iv);const encrypted=Buffer.concat([cipher.update(JSON.stringify(payload),'utf8'),cipher.final()]);return{format:'gridiron-encrypted-backup-v1',cipher:'aes-256-gcm',kdf:'scrypt',salt:salt.toString('base64'),iv:iv.toString('base64'),tag:cipher.getAuthTag().toString('base64'),ciphertext:encrypted.toString('base64')};}finally{key.fill(0);}
}
export async function decryptBackup(backup:EncryptedBackup,password:string):Promise<unknown>{
  validatePassword(password);
  if(backup?.format!=='gridiron-encrypted-backup-v1'||backup.cipher!=='aes-256-gcm'||backup.kdf!=='scrypt')throw new ApiError('Unsupported encrypted backup format.');
  if(![backup.salt,backup.iv,backup.tag,backup.ciphertext].every(value=>typeof value==='string')||backup.salt.length>100||backup.iv.length>100||backup.tag.length>100)throw new ApiError('Invalid encrypted backup.');
  const salt=Buffer.from(backup.salt,'base64'),iv=Buffer.from(backup.iv,'base64'),tag=Buffer.from(backup.tag,'base64');
  if(salt.length!==16||iv.length!==12||tag.length!==16||typeof backup.ciphertext!=='string'||backup.ciphertext.length>100_000_000)throw new ApiError('Invalid encrypted backup.');
  const key=await scrypt(password,salt,32) as Buffer;
  try{const decipher=createDecipheriv('aes-256-gcm',key,iv);decipher.setAuthTag(tag);return JSON.parse(Buffer.concat([decipher.update(Buffer.from(backup.ciphertext,'base64')),decipher.final()]).toString('utf8'));}catch{throw new ApiError('Backup could not be authenticated. Check the password and file integrity.');}finally{key.fill(0);}
}
