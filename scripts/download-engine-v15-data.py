"""Fetch fixed public audit sources and require the recorded exact checksums."""
import hashlib,json,tempfile,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
for source in json.loads((root/'docs/reports/v15-runtime-manifest.json').read_text())['sourceFiles']:
 path=Path(tempfile.gettempdir())/source['filename']
 if path.exists():
  if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('An existing source differs from the recorded audit: '+path.name+'. It was not overwritten.')
  print('Verified existing '+path.name);continue
 partial=path.with_suffix('.v15-download.partial')
 try:
  with urllib.request.urlopen(source['url'],timeout=45) as response,partial.open('xb') as output:
   size=0
   while chunk:=response.read(1024*1024):
    size+=len(chunk)
    if size>source['bytes']:raise ValueError('The published source changed size; a new versioned audit is required.')
    output.write(chunk)
  if size!=source['bytes'] or hashlib.sha256(partial.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('The published source changed since the audit. No mismatched historical data was accepted.')
  partial.rename(path);print('Downloaded and verified '+path.name)
 finally:partial.unlink(missing_ok=True)
