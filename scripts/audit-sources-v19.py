"""Independent source audits; append new reports without changing old inputs."""
import sys,gzip,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import freeze_json
from modeling.reconstruction_v19.outcomes import normalize_box
from modeling.reconstruction_v19.stat_support import TD_STATS
from eccodes import codes_grib_new_from_file,codes_get,codes_release
OUT=ROOT/'artifacts/parallel-v19'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
report={'officialGames':0,'touchdownComparisons':{'NFL':0,'CFB':0},'touchdownMismatches':[],'failedAccountingChecks':[],'weatherFieldIdentities':[],'originalArtifactsModified':False};td={s:read(OUT/'repaired-labels'/(s+'-td-flags.json.gz')) for s in ['NFL','CFB']}
for path in (OUT/'outcomes').glob('*.official.json.gz'):
    obj=read(path);b=obj['box'];s=b['sport'];report['officialGames']+=1
    for ch in b['accountingChecks']:
        if not ch['equal']:report['failedAccountingChecks'].append({'eventId':b['eventId'],**ch})
    derived=td[s]['games'][b['eventId']]
    for pid,row in b['players'].items():
        for stat in TD_STATS:
            if stat not in row['stats'] or not derived['supported'][stat]:continue
            report['touchdownComparisons'][s]+=1;count=derived['players'].get(pid,{}).get(stat,0)
            if count!=row['stats'][stat]:report['touchdownMismatches'].append({'eventId':b['eventId'],'player':pid,'stat':stat,'sourceFlags':count,'official':row['stats'][stat]})
for case in read(ROOT/'docs/reports/parallel-v19-weather-evidence.json')['cases']:
    for field in case['fields']:
        pp=OUT/'weather'/(field['sha256']+'.grib')
        if not pp.exists():
            found=list(OUT.glob('**/'+field['sha256']+'.grib'))
            if len(found)!=1:raise ValueError('Missing bounded weather field')
            pp=found[0]
        if hashlib.sha256(pp.read_bytes()).hexdigest()!=field['sha256']:raise ValueError('GRIB checksum changed')
        with pp.open('rb') as f:
            gid=codes_grib_new_from_file(f)
            try:identity=(str(codes_get(gid,'shortName')),str(codes_get(gid,'typeOfLevel')),int(codes_get(gid,'level')))
            finally:codes_release(gid)
        expected={'temperature':('2t','heightAboveGround',2),'u_wind':('10u','heightAboveGround',10),'v_wind':('10v','heightAboveGround',10)}[field['field']]
        if identity!=expected:raise ValueError('Weather field identity mismatch')
        report['weatherFieldIdentities'].append({'eventId':case['eventId'],'field':field['field'],'decodedIdentity':identity,'sha256':field['sha256'],'confidence':'provider_snapshot_original_operational_object','publishedAt':field['sourceVersionPublishedAt'],'retrievedAt':case['retrievedAt']})
freeze_json(ROOT/'docs/reports/parallel-v19-source-reconciliation.json',report);print(json.dumps(report))
