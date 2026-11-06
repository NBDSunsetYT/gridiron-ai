"""Gated, bounded offline rating fit. Missing market observations stay null.

Existing authorized public PBP editions supply conditional research, not proof
of their original pregame publication. No score or market-price labels are read.
"""
import sys,json,gzip,pickle,hashlib,time,resource,signal,math
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pyarrow as pa
import pyarrow.parquet as pq
from modeling.ratings import fit_ratings,fit_offsets,attach,filter_source_table
from modeling.market_gates_v18 import require_previous,spread_gate,research_exclusions
from modeling.football_data_v15 import NORMALIZER_VERSION,training_before
from modeling.football_source_v18 import eligible_training
from modeling.integration_v22.datasets import protected
from modeling.overnight_v20.state import read,atomic,digest
from modeling.iterative_learning import freeze_json
from modeling.reconstruction_v19.runtime import local_only
OUT=ROOT/'artifacts/market-v18/ratings-r3';CUTOFF='2025-11-15T00:00:00+00:00';SEASON=2025

def load(path):return json.loads(gzip.decompress(Path(path).read_bytes()))

def inputs(sport):
    from modeling.fit import utc
    from modeling.dynamic_v24.stat_data import excluded_validation
    banned=research_exclusions(excluded_validation(),read(ROOT/'artifacts/market-v18/r5/audit-protocol.json'),read(ROOT/'docs/research/specialized-v24-protocols.json')['protocols'])|protected();dataset=pickle.load((ROOT/f'artifacts/engine-v15/{sport}-{NORMALIZER_VERSION}.cache').open('rb'));rows=eligible_training(training_before(dataset,CUTOFF),CUTOFF,banned)
    rows=[r for r in rows if dataset['games'][r['game']]['season']==SEASON];allowed={r['game'] for r in rows};games={g:dataset['games'][g] for g in allowed}
    previous={};rest={}
    for gid,g in sorted(games.items(),key=lambda item:item[1]['firstObservedAt']):
        for t,o in [(g['home'],g['away']),(g['away'],g['home'])]:
            rest[(gid,t)]=(utc(g['firstObservedAt'])-previous[t]).total_seconds()/86400 if t in previous else None
        for t in [g['home'],g['away']]:previous[t]=utc(g['firstObservedAt'])
    differences={(gid,g['home']):rest[(gid,g['home'])]-rest[(gid,g['away'])] if None not in (rest[(gid,g['home'])],rest[(gid,g['away'])]) else None for gid,g in games.items()}
    differences.update({(gid,g['away']):-differences[(gid,g['home'])] if differences[(gid,g['home'])] is not None else None for gid,g in games.items()})
    for r in rows:r['restDifference']=differences.get((r['game'],r['o']))
    path=Path('/tmp/gridiron-'+('nfl-pbp-' if sport=='NFL' else 'cfb-public-pbp-')+str(SEASON)+'.parquet');version=hashlib.sha256(path.read_bytes()).hexdigest()
    names=['game_id','season','time_of_day','wallclock','posteam','defteam','pos_team_id','def_pos_team_id','home_team','homeTeamId','epa','EPA','down','pass_attempt','rush_attempt','rush','sack','no_play','penalty_no_play']
    schema=pq.ParquetFile(path).schema.names;hidden=[int(g.split(':')[-1]) for g in banned if g.startswith('cfb:espn:')] if sport=='CFB' else [g for g in banned if '_' in g and g[:4].isdigit()]
    table=pq.read_table(path,columns=[n for n in names if n in schema],filters=[('game_id','not in',hidden),('season','=',SEASON)])
    timefield='time_of_day' if sport=='NFL' else 'wallclock';times=table[timefield].to_pylist();ids=table['game_id'].to_pylist();mask=[]
    def game_id(v):return 'cfb:espn:'+str(int(v)) if sport=='CFB' else str(v)
    for at,gid in zip(times,ids):
        try:mask.append(game_id(gid) in allowed and utc(at)<utc(CUTOFF))
        except (ValueError,TypeError):mask.append(False)
    table=filter_source_table(table,mask);epa=[];skipped=Counter()
    def team_id(v):
        if v is None or isinstance(v,float) and not math.isfinite(v):return None
        return 'cfb:espn:'+str(int(v)) if sport=='CFB' else str(v)
    for r in table.to_pylist():
        value=r.get('epa' if sport=='NFL' else 'EPA');gid=game_id(r['game_id']);off=team_id(r.get('posteam' if sport=='NFL' else 'pos_team_id'));defense=team_id(r.get('defteam' if sport=='NFL' else 'def_pos_team_id'))
        if value is None or not math.isfinite(value) or not off or not defense or not r.get('down') or r.get('no_play') or r.get('penalty_no_play'):
            skipped['unsupported_or_missing']+=1;continue
        if not any(r.get(k) for k in ('pass_attempt','rush_attempt','rush','sack')):continue
        epa.append({'game':gid,'sport':sport,'season':SEASON,'o':off,'d':defense,'home':int(off==games[gid]['home']),'epa':float(value),'at':utc(r[timefield]).isoformat(),'eventAt':games[gid]['firstObservedAt'],'restDifference':differences.get((gid,off)),'sourceVersion':version,'availableAt':None})
    first={}
    for r in epa:first[r['game']]=min(first.get(r['game'],r['eventAt']),r['at'])
    for r in epa:r['eventAt']=first[r['game']]
    assert not ({r['game'] for r in rows}|{r['game'] for r in epa})&banned
    return rows,epa,{'sourceSHA256':version,'rows':len(epa),'supportedGames':len({r['game'] for r in epa}),'excludedGameIdsSHA256':digest(sorted(banned)),'excludedGameIdsCount':len(banned),'skipped':dict(skipped),'publicationAvailabilityVerified':False,'restDefinition':'Difference in days between first verified PBP timestamps; kickoff/end-of-game rest not independently certified','retrievedForResearchAt':datetime.now(timezone.utc).isoformat()}

def register():
    require_previous({'1':read(ROOT/'artifacts/market-v18/gate1.json',{})},2)
    files=[Path(__file__),ROOT/'modeling/ratings.py',ROOT/'modeling/football_v15.py',ROOT/'modeling/engine_v15_routes.py',ROOT/'modeling/market_gates_v18.py'];inputs={}
    for sport in ('NFL','CFB'):
        for p in [ROOT/f'artifacts/engine-v15/{sport}-{NORMALIZER_VERSION}.cache',ROOT/'artifacts/market-v18/r5/models'/(sport+'-'+CUTOFF[:10]+'.json.gz'),Path('/tmp/gridiron-'+('nfl-pbp-' if sport=='NFL' else 'cfb-public-pbp-')+str(SEASON)+'.parquet')]:inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    freeze_json(OUT/'protocol.json',{'operation':'conditional_offline_epa_ratings_and_mle_offsets','code':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'inputHashes':inputs,'cutoff':CUTOFF,'season':SEASON,'leagues':['NFL','CFB'],'ridgeGrid':[1.,10.,100.],'offsetRidge':1.,'historicalFinalScoresAllowed':False,'marketPricesInvented':False,'protectedGamesAllowed':False,'tuningOn500Audit':False,'holdoutSpreadRequirement':.80,'quotes':[],'quoteLimitation':'Available schedule columns lack verified book, capture time and closing provenance; no qualified independent closing-spread cohort exists'})

def run():
    local_only();require_previous({'1':read(ROOT/'artifacts/market-v18/gate1.json',{})},2);protocol=read(OUT/'protocol.json')
    for name,sha in protocol['code'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Registered Stage 2 source changed')
    for name,sha in protocol['inputHashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Registered Stage 2 input edition changed')
    results=[]
    for sport in protocol['leagues']:
        start=time.process_time()
        try:
            rows,epa,coverage=inputs(sport);atomic(OUT/sport/'source-coverage.json',coverage)
            if not epa:raise ValueError('No eligible EPA rows remain after protected/exposed campaign exclusions; no fitting or gate relaxation')
            rating=fit_ratings(epa,sport,SEASON,CUTOFF);freeze_json(OUT/sport/'ratings-only.json.gz',rating);models=load(ROOT/'artifacts/market-v18/r5/models'/(sport+'-'+CUTOFF[:10]+'.json.gz'));base=next(m for m in models.values() if 'passTouchdown' in m);rating=fit_offsets(rows,base,rating);model=attach(base,rating)
            freeze_json(OUT/sport/'ratings.json.gz',rating);freeze_json(OUT/sport/'model.json.gz',model)
            result={'sport':sport,'status':'conditional_candidate_fitted','version':model['version'],'modelSHA256':model['sha256'],'ratingsSHA256':rating['sha256'],'ridgeAlpha':rating['ridgeAlpha'],'blockedCV':rating['blockedCV'],'homeFieldCoefficient':rating['homeFieldCoefficient'],'restCoefficient':rating['restCoefficient'],'weeklyProcessVariance':rating['weekly']['processVariance'],'weeklyRegressionToMean':rating['weekly']['regressionToMean'],'trainedHeads':sorted(rating['offsets']),'sourceCoverage':coverage,'forecastValidationGames':0,'productionEligible':False,'cpuSeconds':time.process_time()-start}
        except (ValueError,KeyError,StopIteration) as e:result={'sport':sport,'status':'withheld','reason':str(e),'cpuSeconds':time.process_time()-start,'productionEligible':False}
        results.append(result);atomic(OUT/(sport+'-receipt.json'),result);print(json.dumps(result),flush=True)
    gate=spread_gate(protocol['quotes']);gate['reason']=protocol['quoteLimitation'];gate['stage3Allowed']=False;gate['CLVSample']=0;gate['fittedBlendWeights']=None
    atomic(OUT/'gate2.json',gate);atomic(OUT/'results.json',{'ratings':results,'gate2':gate,'productionWrites':0,'newQualifiedForecasts':0});print('Holdout model/market spread correlation: '+str(gate['spreadCorrelation'])+'; qualified quotes: '+str(gate['qualifiedGames']),flush=True)
    return gate

if __name__=='__main__':
    import argparse,re
    parser=argparse.ArgumentParser();parser.add_argument('--register',action='store_true');parser.add_argument('--season',type=int,choices=(2024,2025),default=SEASON);parser.add_argument('--cutoff',default=CUTOFF);parser.add_argument('--revision',default='ratings-r3');args=parser.parse_args()
    from modeling.fit import utc
    if not re.fullmatch(r'ratings-r[0-9]+',args.revision):raise ValueError('A new bounded research revision name is required')
    CUTOFF=utc(args.cutoff).isoformat();SEASON=args.season;OUT=ROOT/'artifacts/market-v18'/args.revision
    if args.register:register()
    else:
        signal.signal(signal.SIGALRM,lambda *a: (_ for _ in ()).throw(TimeoutError('Bounded Stage 2 fit stopped')));signal.alarm(360);resource.setrlimit(resource.RLIMIT_CPU,(300,305));resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));gate=run();raise SystemExit(0 if gate['passed'] else 2)
