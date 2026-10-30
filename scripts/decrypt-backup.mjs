/** Standalone recovery utility: passphrase comes from stdin; output is private.
 * Supports original v1 envelopes and bounded gzip/AAD v2 evidence archives.
 */
import {readFile,writeFile,stat} from 'node:fs/promises';
import {createDecipheriv,scrypt as scryptCallback} from 'node:crypto';
import {gunzip as gunzipCallback} from 'node:zlib';
import {promisify} from 'node:util';
const EXPANDED_LIMIT=160_000_000,CIPHERTEXT_LIMIT=100_000_000;
const [inputPath,outputPath]=process.argv.slice(2);
if(!inputPath||!outputPath||process.argv.length!==4){
 console.error('Usage: node scripts/decrypt-backup.mjs encrypted.json recovered.json < password-file');
 console.error('Provide the passphrase on stdin, never as a command-line argument. Protect plaintext output.');process.exit(1);
}
try{
 if((await stat(inputPath)).size>CIPHERTEXT_LIMIT+4096)throw Error('Archive size exceeds the recovery bound.');
 const backup=JSON.parse(await readFile(inputPath,'utf8'));
 if(!['gridiron-encrypted-backup-v1','gridiron-encrypted-backup-v2'].includes(backup.format)||backup.cipher!=='aes-256-gcm'||backup.kdf!=='scrypt')throw Error('Unsupported backup format.');
 const compressed=backup.format==='gridiron-encrypted-backup-v2';
 if(compressed&&(backup.compression!=='gzip'||!Number.isSafeInteger(backup.uncompressedBytes)||backup.uncompressedBytes<1||backup.uncompressedBytes>EXPANDED_LIMIT))throw Error('Invalid compressed backup metadata.');
 if(![backup.salt,backup.iv,backup.tag,backup.ciphertext].every(value=>typeof value==='string')||backup.salt.length>100||backup.iv.length>100||backup.tag.length>100||backup.ciphertext.length>CIPHERTEXT_LIMIT)throw Error('Malformed backup encryption metadata.');
 const salt=Buffer.from(backup.salt,'base64'),iv=Buffer.from(backup.iv,'base64'),tag=Buffer.from(backup.tag,'base64');
 if(salt.length!==16||iv.length!==12||tag.length!==16)throw Error('Malformed backup encryption metadata.');
 let passwordInput='';for await(const chunk of process.stdin){passwordInput+=chunk.toString();if(passwordInput.length>130)throw Error('Passphrase input too long.');}
 const password=passwordInput.replace(/\r?\n$/,'');if(password.length<12||password.length>128)throw Error('Passphrase must contain 12–128 characters.');
 const key=await promisify(scryptCallback)(password,salt,32);let plaintext;
 try{
  const decipher=createDecipheriv('aes-256-gcm',key,iv);
  if(compressed)decipher.setAAD(Buffer.from(JSON.stringify(['gridiron-encrypted-backup-v2','gzip',backup.uncompressedBytes]),'utf8'));
  decipher.setAuthTag(tag);plaintext=Buffer.concat([decipher.update(Buffer.from(backup.ciphertext,'base64')),decipher.final()]);
 }finally{key.fill(0);}
 if(compressed){plaintext=await promisify(gunzipCallback)(plaintext,{maxOutputLength:Math.min(EXPANDED_LIMIT,backup.uncompressedBytes+1)});if(plaintext.length!==backup.uncompressedBytes)throw Error('Archive expansion mismatch.');}
 if(plaintext.length>EXPANDED_LIMIT)throw Error('Archive expansion exceeds the recovery bound.');
 const payload=JSON.parse(plaintext.toString('utf8'));if(![1,2].includes(payload.version)||!payload.ledger)throw Error('Unsupported recovered payload.');
 await writeFile(outputPath,JSON.stringify(payload,null,2)+'\n',{mode:0o600,flag:'wx'});plaintext.fill(0);
 console.log('Recovery succeeded. Plaintext output was written with owner-only permissions.');
}catch(error){console.error(error?.code==='EEXIST'?'Output already exists; choose a new file.':'Recovery failed. Check the passphrase, backup format, and paths. No successful recovery was written.');process.exit(1);}
