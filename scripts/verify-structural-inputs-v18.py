"""Read-only source, chronology and artifact-integrity verification; no MC."""
import gzip,hashlib,json,pickle,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import digest
from modeling.structural_v18.data import stamp
OUT=ROOT/'artifacts/structural-v18';cpu=time.process_time()
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
protocol=read(OUT/'protocol.json');sources=0
for item in protocol['sourceFiles']:
    if hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Locked historical source changed')
    sources+=1
raw={s:pickle.load((ROOT/'artifacts/learning-v16/datasets'/(s+'-repaired.pickle')).open('rb')) for s in ['NFL','CFB']};models={};whole_games=0;rotation_rows=0
for path in (OUT/'full-models').glob('*.json.gz'):
    m=read(path)
    if 'sport' not in m:continue
    if digest({k:v for k,v in m.items() if k!='sha256'})!=m['sha256']:raise ValueError('Fitted parameter hash changed')
    if m['sport'] in raw:
        for gid in m['trainingGameIds']:
            if stamp(raw[m['sport']]['games'][gid]['lastObservedAt'])>=stamp(m['fittingCutoff']):raise ValueError('A training game extended past fit cutoff')
            whole_games+=1
    else:
        for hs in m.get('rotationTeams',m['teams']).values():
            for g in hs:
                if stamp(g['at'])+6*3600>=stamp(m['cutoff']):raise ValueError('Future NBA rotation evidence')
                rotation_rows+=1
    models[m['sha256']]=m
runs=0
for path in (OUT/'full-games').glob('*/*/*.forecast.json.gz'):
    f=read(path)['forecast'];m=models[f['inputDataVersion']]
    if stamp(f['evidenceCutoff'])>=stamp(f['eventStart']):raise ValueError('Future observation in a forecast')
    if f['sport'] in raw and f['eventStart']<=m['fittingCutoff']:raise ValueError('Cohort forecast precedes fitted inputs')
    runs+=1
root=read(ROOT/'docs/reports/structural-v18-root-causes-v3.json')
for path,sha in root['sourceChecksums'].items():
    if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise ValueError('Original development record changed')
report={'sourceFiles':sources,'modelArtifacts':len(models),'forecastRuns':runs,'wholeGameTrainingMembershipChecks':whole_games,'rotationHistoryChecks':rotation_rows,'originalDevelopmentFiles':len(root['sourceChecksums']),'violations':0,'cpuSeconds':time.process_time()-cpu,'financialDatabaseOperations':0,'originalPublicationVerified':False};(OUT/'input-integrity.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n');print(json.dumps(report))
