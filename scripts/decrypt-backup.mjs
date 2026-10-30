/** Recovery utility: password comes from stdin; plaintext is written with owner-only permissions. */
import { readFile, writeFile } from 'node:fs/promises';
import { createDecipheriv, scrypt as scryptCallback } from 'node:crypto';
import { promisify } from 'node:util';
const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath || process.argv.length !== 4) {
  console.error('Usage: node scripts/decrypt-backup.mjs encrypted.json recovered.json < password-file');
  console.error('Provide the passphrase on stdin, never as a command-line argument. Protect plaintext output.');
  process.exit(1);
}
try {
  const backup = JSON.parse(await readFile(inputPath, 'utf8'));
  if (backup.format !== 'gridiron-encrypted-backup-v1' || backup.cipher !== 'aes-256-gcm' || backup.kdf !== 'scrypt') throw new Error('Unsupported backup format.');
  const salt = Buffer.from(backup.salt, 'base64'), iv = Buffer.from(backup.iv, 'base64'), tag = Buffer.from(backup.tag, 'base64');
  if (salt.length !== 16 || iv.length !== 12 || tag.length !== 16) throw new Error('Malformed backup encryption metadata.');
  let passwordInput = '';
  for await (const chunk of process.stdin) {
    passwordInput += chunk.toString();
    if (passwordInput.length > 130) throw new Error('Passphrase input too long.');
  }
  const password = passwordInput.replace(/\r?\n$/, '');
  if (password.length < 12 || password.length > 128) throw new Error('Passphrase must contain 12–128 characters.');
  const key = await promisify(scryptCallback)(password, salt, 32);
  const decipher = createDecipheriv('aes-256-gcm', key, iv);
  decipher.setAuthTag(tag);
  const plaintext = Buffer.concat([decipher.update(Buffer.from(backup.ciphertext, 'base64')), decipher.final()]);
  key.fill(0);
  const payload = JSON.parse(plaintext.toString('utf8'));
  if (![1, 2].includes(payload.version) || !payload.ledger) throw new Error('Unsupported recovered payload.');
  await writeFile(outputPath, JSON.stringify(payload, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
  plaintext.fill(0);
  console.log('Recovery succeeded. Plaintext output was written with owner-only permissions.');
} catch (error) {
  console.error(error?.code === 'EEXIST' ? 'Output already exists; choose a new file.' : 'Recovery failed. Check the passphrase, backup format, and paths. No successful recovery was written.');
  process.exit(1);
}
