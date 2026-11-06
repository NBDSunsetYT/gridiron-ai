"""Attach inherited provenance without duplicating historical stat collections."""
import sys,json,gzip,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import freeze_json
OUT=ROOT/'artifacts/parallel-v19';collected=datetime.now(timezone.utc).isoformat();records=[]
for sport in ['NFL','CFB']:
    path=OUT/'repaired-labels'/(sport+'-td-flags.json.gz');a=json.loads(gzip.decompress(path.read_bytes()));sources=[]
    for source in a['sources']:
        year=Path(source['path']).stem[-4:];base='https://github.com/nflverse/nflverse-data/releases/download/pbp/' if sport=='NFL' else 'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_pbp/';sources.append({'sourceRef':source['sha256'],'source':base+'play_by_play_'+year+'.parquet','publishedAt':None,'originalNetworkRetrievedAt':None,'retrievedFromOwnedArchiveAt':collected,'confidence':'unverified_original_publication_timestamp','version':source['sha256']})
    records.append({'sport':sport,'collection':str(path.relative_to(ROOT)),'collectionSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sourceRefs':[s['sourceRef'] for s in sources],'inheritedBy':'Every game/stat/player count in this derived collection; shared references avoid per-record repeated dataset metadata.','sources':sources,'publicationQualifiedForHistoricalForecast':False,'reliability':'Explicit source flags independently reconciled against final boxes; original pregame publication/version availability remains unverified.','collectionTimestampMeaning':'Time this metadata collector read the owned immutable cache, not time the publisher first released statistics.'})
freeze_json(ROOT/'docs/reports/parallel-v19-label-provenance.json',records)
