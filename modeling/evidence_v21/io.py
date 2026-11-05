"""Bounded public-source IO, independent of immutable V20 caches."""
import json,gzip,hashlib,time,re,html
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlparse
from urllib.error import HTTPError
from datetime import datetime,timezone
from ..overnight_v20.state import read,atomic
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'artifacts/overnight-v21'
def fetch(url,maximum_bytes=8000000):
    if urlparse(url).scheme!='https' or not urlparse(url).hostname:raise ValueError('Public HTTPS source required')
    if not 1<=maximum_bytes<=16000000:raise ValueError('Bounded public document size required')
    from ..reconstruction_v19.runtime import local_only
    local_only();key=hashlib.sha256((url if maximum_bytes==8000000 else url+'#bounded-bytes='+str(maximum_bytes)).encode()).hexdigest();path=OUT/'sources/receipts'/(key+'.json');old=read(path)
    if old:return (gzip.decompress((ROOT/old['object']).read_bytes()) if old.get('object') else None),old
    r={'url':url,'retrievedAt':datetime.now(timezone.utc).isoformat()};body=None
    for attempt in range(2):
        try:
            with urlopen(Request(url,headers={'User-Agent':'GRIDIRON-AI-Public-Research/21'}),timeout=20) as response:
                candidate=response.read(maximum_bytes+1)
                if len(candidate)>maximum_bytes:raise ValueError('Source exceeds declared bounded document cap')
                body=candidate
                sha=hashlib.sha256(body).hexdigest();p=OUT/'sources/objects'/(sha+'.gz');p.parent.mkdir(parents=True,exist_ok=True)
                if not p.exists():p.write_bytes(gzip.compress(body,compresslevel=3,mtime=0))
                r.update(httpStatus=response.status,finalUrl=response.url,sourceVersion=sha,object=str(p.relative_to(ROOT)),bytes=len(body),lastModified=response.headers.get('Last-Modified'),contentType=response.headers.get('Content-Type'));break
        except HTTPError as e:
            r['httpStatus']=e.code
            if e.code not in (429,500,502,503,504):break
        except (OSError,ValueError) as e:r['error']=type(e).__name__
        if attempt==0:time.sleep(1)
    atomic(path,r);time.sleep(.15);return body,r
def published_metadata(body):
    text=body.decode(errors='replace');values={k:[] for k in ('datePublished','dateModified')}
    for k in values:values[k]=sorted(set(html.unescape(v) for v in re.findall(r'"'+k+r'"\s*:\s*"([^"<>]+)"',text)))
    return values
def canonical_article(body,url):
    """Related galleries/news have their own dates; never mix their timestamps."""
    from urllib.parse import urlsplit
    def identity(u):
        parsed=urlsplit(u);return (str(parsed.hostname or '').removeprefix('www.'),parsed.path.rstrip('/'))
    expected=identity(url);found=[]
    def visit(node):
        if isinstance(node,list):
            for item in node:visit(item)
        elif isinstance(node,dict):
            if node.get('@type') in ('NewsArticle','Article'):
                main=node.get('mainEntityOfPage');main=main.get('@id') if isinstance(main,dict) else main
                ids=[identity(u) for u in [node.get('url'),main,node.get('@id')] if isinstance(u,str) and urlsplit(u).scheme in ('http','https')]
                if ids and all(i==expected for i in ids):found.append(node)
            if '@graph' in node:visit(node['@graph'])
    for raw in re.findall(r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>',body.decode(errors='replace'),re.S|re.I):
        try:visit(json.loads(raw))
        except json.JSONDecodeError:continue
    if len(found)!=1:raise ValueError('Exactly one canonical article required; related-content dates are not authoritative')
    return found[0]
def pdf_link(body):
    text=html.unescape(body.decode(errors='replace'));links=re.findall(r'https://[^\s"<>]+\.pdf(?:\?[^\s"<>]*)?',text,re.I)
    preferred=[u for u in links if 'sidearm' in u or 'storage.googleapis' in u]
    return (preferred or links or [None])[0]
