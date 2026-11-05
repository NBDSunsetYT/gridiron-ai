"""One independently checkpointed chronological cohort, with frozen forecasts.
Final outcomes are queried by the evaluator only after point forecasts AND all
same-game MC variants are written. Model fitting never reads these grade files.
"""
import os,sys,json,gzip,pickle,time,copy,hashlib,csv,math
from pathlib import Path
from collections import defaultdict
from datetime import timedelta
import numpy as np
from .state import atomic,digest
from .sources import protocol,fetch
from . import data as features,models,football,nba
from ..iterative_learning import freeze_json,distribution_errors,unrealism_flags
from ..reconstruction_v19.evidence import aware
from ..reconstruction_v19.outcomes import normalize_box,player_outcome
from ..reconstruction_v19 import football_rules as football19,nba as nba19
from ..reconstruction_v19.football_fit import enrich as football_enrich
from ..reconstruction_v19.oof_variance import estimate as oof_variance
from ..reconstruction_v19.nba_fit import enrich as nba_enrich
from ..structural_v18.nba import fit_nba
from ..football_v15 import fit_football
from ..structural_v18.models import Projection,FAMILIES,OPPORTUNITY
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'artifacts/overnight-v20'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def save_pickle(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('Immutable fitted models already exist')
    with path.open('xb') as f:pickle.dump(value,f)
def lineup(g,evidence):
    result={};cutoff=aware(g['at'])-timedelta(minutes=30)
    for team in [g['home'],g['away']]:
        rs=[r for r in evidence['facts'] if r['eventId']==g['id'] and r['teamId']==team and r['playerId'] and aware(r['publishedAt'])<cutoff];inactive=sorted({r['playerId'] for r in rs if r['status'].lower() in ['out','inactive','injured_reserve']});result[team]={'inactive':inactive,'verified':False,'injuriesComplete':False,'source':rs[-1]['source'] if rs else None,'availableAt':max((r['publishedAt'] for r in rs),default=None),'missingMeansHealthy':False,'questionableWeights':None}
    return result

def training_rows(packets,cutoff,max_games=500):
    eligible=[g for g in packets if aware(g['end'])+timedelta(hours=6)<aware(cutoff)];chosen={g['id'] for g in eligible[-max_games:]};history=defaultdict(list);rows=[]
    for g in eligible:
        if g['id'] in chosen:
            for team in [g['home'],g['away']]:
                for r in features.features_for(g,team,history,g['sport']):
                    if r['player'].split(':')[-1].startswith('-'):continue
                    obs={'stats':g['teams'][team]['totals']} if r['player']=='__team__' else g['teams'][team]['players'].get(r['player']);r['y']=obs['stats'].get(r['stat'],0.) if obs else 0.;r['opportunity']=obs['stats'].get(OPPORTUNITY.get(r['stat'],''),0.) if obs else 0.;rows.append(r)
        for team in [g['home'],g['away']]:history[team].append(g)
    return rows,chosen

def point_fit(rows):
    grouped=defaultdict(list)
    for r in rows:grouped[(r['player']=='__team__',r['stat'])].append(r)
    fitted={}
    for key,rs in grouped.items():
        if len(rs)<20:continue
        for family in FAMILIES:fitted[(key,family)]=Projection(family).fit(rs)
    return fitted

def point_predict(fitted,games,packets,evidence):
    history=defaultdict(list)
    for g in packets:
        for team in [g['home'],g['away']]:history[team].append(g)
    outputs=[];allmaps={}
    for g in games:
        rows=[]
        for team in [g['home'],g['away']]:rows.extend(features.features_for(g,team,history,g['sport']))
        rows=[r for r in rows if not r['player'].split(':')[-1].startswith('-')];groups=defaultdict(list)
        for r in rows:groups[(r['player']=='__team__',r['stat'])].append(r)
        predicted={};lf=lineup(g,evidence);mapping=defaultdict(lambda:defaultdict(dict))
        for key,rs in sorted(groups.items(),key=lambda kv:(kv[0][1] not in ('minutes','passingAttempts','targets','carries'),kv[0])):
            identity=lambda r:(r['team'],r['player'])
            for family in FAMILIES:
                m=fitted.get((key,family))
                if m is None:continue
                op=None
                if family=='hybrid' and getattr(m,'rate',None) is not None:
                    lookup=predicted.get(((key[0],OPPORTUNITY[key[1]]),'ridge'))
                    if lookup is None:continue
                    op=np.array([lookup[identity(r)] for r in rs])
                values=m.predict(rs,op);predicted[(key,family)]={identity(r):float(v) for r,v in zip(rs,values)}
            for row in rs:
                pred={f:predicted[(key,f)][identity(row)] for f in FAMILIES if (key,f) in predicted};out=row['player'] in lf[row['team']]['inactive'];raw=pred.copy()
                if out:pred={k:0. for k in pred}
                if any(not math.isfinite(v) for v in pred.values()):raise ValueError('Nonfinite point forecast')
                outputs.append({'gameId':g['id'],'team':row['team'],'player':row['player'],'stat':row['stat'],'role':row['role'],'featureCutoff':row['featureCutoff'],'featureSha256':digest(row['x']),'predictions':pred,'knownOutAtCutoff':out,'rawBeforeKnownOut':raw if out else None,'injuryEvidence':'partial' if lf[row['team']]['source'] else 'unavailable','cohort':g['cohort'],'season':g['season']})
                if 'ridge' in pred:mapping[row['team']][row['player']][row['stat']]=pred['ridge']
        allmaps[g['id']]={t:dict(players) for t,players in mapping.items()}
    return outputs,allmaps

def nba_box(gid,packets):
    g=next(g for g in packets if g['id']==gid);players={}
    for team,t in g['teams'].items():
        for pid,p in t['players'].items():players['nba:espn:'+pid]={'team':team,'stats':p['stats']}
    return {'eventId':gid,'sport':'NBA','scores':{t:v['totals']['score'] for t,v in g['teams'].items()},'players':players,'supportedStatisticsByTeam':{t:list(features.BASKETBALL) for t in g['teams']},'outcomesVerified':True,'notForPregameFeatures':True}

_NFL_MAP=None;_SCHEDULE=None
def official_box(g,packets):
    if g['sport']=='NBA':return nba_box(g['id'],packets)
    path=OUT/'outcomes'/(g['id'].replace(':','_')+'.json.gz')
    if path.exists():return read(path)['box']
    global _NFL_MAP,_SCHEDULE
    if g['sport']=='NFL':
        if _NFL_MAP is None:
            import pyarrow.parquet as pq
            _NFL_MAP={};rs=pq.read_table(ROOT/'artifacts/parallel-v19/sources/players.parquet',columns=['gsis_id','espn_id']).to_pylist()
            for r in rs:
                if r['espn_id'] and r['gsis_id']:
                    key=str(r['espn_id']).removesuffix('.0')
                    if key in _NFL_MAP and _NFL_MAP[key]!=r['gsis_id']:raise ValueError('Ambiguous NFL ID crosswalk')
                    _NFL_MAP[key]=r['gsis_id']
            _SCHEDULE={r['game_id']:r for r in csv.DictReader((ROOT/'artifacts/parallel-v19/sources/nfl-games.csv').open())}
        provider=str(_SCHEDULE[g['id']]['espn']);league='nfl'
    else:provider=g['id'].split(':')[-1];league='college-football'
    url=f'https://site.api.espn.com/apis/site/v2/sports/football/{league}/summary?event={provider}';raw,receipt=fetch(url)
    if raw is None:raise ValueError('Official final box unavailable: '+str(receipt.get('httpStatus',receipt.get('error'))))
    payload=json.loads(raw)
    if str(payload['header']['id'])!=provider:raise ValueError('Official final event identity mismatch')
    box=normalize_box(payload,g['sport'],g['id'],g['home'],g['away'],_NFL_MAP);freeze_json(path,{'box':box,'source':receipt,'forGradingOnly':True});return box

def point_grade(rows,boxes,sport):
    grades=[]
    for r in rows:
        box=boxes.get(r['gameId'])
        if not box:continue
        if r['player']=='__team__':
            y=box['scores'].get(r['team']) if r['stat']=='score' else box.get('teamStatTotals',{}).get(r['team'],{}).get(r['stat'])
        else:y,_=player_outcome(box,('nba:espn:'+r['player']) if sport=='NBA' else r['player'],r['team'],r['stat'])
        if y is not None:grades.append(r|{'actual':y})
    return grades

def mc_grade(f,g,box,frame):
    player_rows=[];missing=[];zero_count=0
    zero={'mean':0.,'median':0,'interval90':[0,0],'histogram':[{'value':0,'count':f['simulations']}]}
    for r in frame:
        if r['gameId']!=g['id'] or r['player']=='__team__':continue
        pid='nba:espn:'+r['player'] if g['sport']=='NBA' else r['player'];d=f['players'].get(pid,{}).get(r['stat'])
        if r['stat'] not in next(iter(f['players'].values())):missing.append({'player':pid,'stat':r['stat'],'reason':'unsupported_simulation_statistic'});continue
        if d is None:d=zero;zero_count+=1
        y,why=player_outcome(box,pid,r['team'],r['stat'])
        if y is None:missing.append({'player':pid,'stat':r['stat'],'reason':why});continue
        player_rows.append({'id':pid,'team':r['team'],'stat':r['stat'],'role':r['role'],'knownOutAtCutoff':r['knownOutAtCutoff'],**distribution_errors(d,y)})
    h,a=g['home'],g['away'];scores=box['scores'];p=f['homeWinProbability'];return {'gameId':g['id'],'sport':g['sport'],'cohort':g['cohort'],'season':g['season'],'probability':p,'truth':int(scores[h]>scores[a]),'ties':scores[h]==scores[a],'score':[distribution_errors(f['scoreDistributions'][t],scores[t]) for t in [h,a]],'players':player_rows,'missing':missing,'explicitModelImpliedZeroDistributions':zero_count,'zeroPolicy':'The predefined earlier-roster frame includes actors not participating under a candidate hypothesis. These are explicit zero outcomes of that model, not fabricated source observations.','unmodeledActualParticipants':sum(pid not in f['players'] for pid in box['players']),'outcomesVerified':True,'publishedInputCoverageComplete':False}

def run(sport,cohort,preliminary=False):
    p=protocol();games=[g for g in p['selection'][sport] if g['cohort']==cohort];job=f'{sport}-{cohort}';folder=OUT/'experiments'/os.environ.get('GRIDIRON_RESEARCH_REVISION','r1')/'cohorts'/job;folder.mkdir(parents=True,exist_ok=True);start=time.monotonic();before=time.process_time();failures=[]
    if not games:return {'status':'completed','cpuSeconds':time.process_time(),'games':0}
    evidence=read(OUT/'evidence'/(sport+'-aligned-v3.json.gz'));cutoff=(min(aware(g['at']) for g in games)-timedelta(hours=6)).isoformat();packets=features.packets(sport);data=features.archives(sport);rows,training_ids=training_rows(packets,cutoff)
    fitpath=folder/'point-models.pickle'
    if fitpath.exists():fitted=pickle.load(fitpath.open('rb'))
    else:fitted=point_fit(rows);save_pickle(fitpath,fitted)
    pointpath=folder/'point-forecasts.json.gz'
    if pointpath.exists():saved=read(pointpath);predictions=saved['rows'];allmaps=saved['opportunities']
    else:
        predictions,allmaps=point_predict(fitted,games,packets,evidence);freeze_json(pointpath,{'sport':sport,'cohort':cohort,'fitCutoff':cutoff,'trainingGames':sorted(training_ids),'rows':predictions,'opportunities':allmaps,'historicalSourcePublicationVerified':False,'reservedFinalOpened':False,'sourceProtocolSha256':hashlib.sha256((OUT/'protocol-effective.json').read_bytes()).hexdigest(),'savedBeforeCurrentCohortGrading':True})
    print(json.dumps({'stage':'points_frozen','job':job,'predictions':len(predictions),'cpuSeconds':time.process_time()-before}),flush=True)
    mpath=folder/'simulation-model.json.gz'
    if mpath.exists():base=read(mpath)
    elif sport=='NBA':
        base=nba_enrich(fit_nba(data,cutoff,'v20-chronological-owned-boxes','rotation_bootstrap'),data,cutoff);models.enrich_rebounds(base,data,cutoff);base['sha256']=digest({k:v for k,v in base.items() if k!='sha256'});freeze_json(mpath,base)
    else:
        eligible={gid for gid,g in data['games'].items() if aware(g['lastObservedAt'])+timedelta(hours=6)<aware(cutoff)};play_rows=[r for r in data['rows'] if r['game'] in eligible and aware(r['at'])<aware(cutoff)];base=football_enrich(fit_football(play_rows,sport,cutoff,'v20-chronological-owned-pbp'),play_rows,'team_eb_frailty');variance=oof_variance(play_rows,data['games'],cutoff);base.update(version=football19.VERSION,completionFrailtySD=variance['sd'],completionFrailtyEvidence=variance,qbContinuity=models.fit_qb_continuity(base),gameSeasons={gid:g['season'] for gid,g in data['games'].items() if gid in eligible});base=json.loads(json.dumps(base,sort_keys=True));base['sha256']=digest({k:v for k,v in base.items() if k!='sha256'});freeze_json(mpath,base)
    variants=['v19_reference','buzzer','share_buzzer'] if sport=='NBA' else ['v19_reference','volume_bridge','qb_mixture'];boxes={};runs=[]
    for g in games:
        if not g['fullGame']:continue
        lf=lineup(g,evidence);seed=int(hashlib.sha256(('v20:'+g['id']).encode()).hexdigest()[:10],16);forecasts={}
        for variant in variants:
            fp=folder/'forecasts'/variant/(g['id'].replace(':','_')+'.json.gz')
            try:
                if fp.exists():archive=read(fp);f=archive['forecast']
                else:
                    m=models.refresh_context(copy.deepcopy(base),data,g);m['forecastSeason']=g['season']
                    if sport=='NBA':
                        m['projectedMinutes']={t:{pid:stats['minutes'] for pid,stats in allmaps[g['id']][t].items() if pid!='__team__' and 'minutes' in stats} for t in [g['home'],g['away']]};m['reboundVariant']=variant
                        if variant!='v19_reference':m['version']=nba.VERSION
                        engine=nba19 if variant=='v19_reference' else nba;m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});f=engine.simulate_nba(m,g['home'],g['away'],g['at'],10000,seed,lineups=lf)
                    else:
                        if variant!='v19_reference':
                            m.update(version=football.VERSION,forecastSeason=g['season'],passRateShift=models.volume_shift(m,allmaps[g['id']],[g['home'],g['away']]))
                            if variant=='qb_mixture':m['qbPlans']=models.qb_plans(m,[g['home'],g['away']],lf)
                        engine=football19 if variant=='v19_reference' else football;m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});f=engine.simulate_football(m,g['home'],g['away'],g['at'],10000,seed,lineups=lf,representative_games=0)
                    if unrealism_flags(f):raise ValueError('Full-game accounting validation failed')
                    # Compact per-game patches + shared fitted model reproduce it.
                    context={k:m[k] for k in ['histories','rotationTeams','gameSeasons','contextCutoff'] if k in m};contextSha=digest(context);freeze_json(folder/'contexts'/(contextSha+'.json.gz'),context)
                    patch={k:m[k] for k in ['projectedMinutes','reboundVariant','version','forecastSeason','passRateShift','qbPlans','sha256'] if k in m};archive={'game':g,'variant':variant,'forecast':f,'modelPatch':patch,'sharedModelSha256':base['sha256'],'contextSha256':contextSha,'lineups':lf,'inputFeaturesSha256':digest(allmaps[g['id']]),'reservedFinalOpened':False,'retrospectiveCorrectedHistory':True,'completePointInTimeInputCoverage':False,'dependencies':{k:__import__(k).__version__ for k in ['numpy','scipy','sklearn']}};freeze_json(fp,archive)
                forecasts[variant]=f;runs.append({'gameId':g['id'],'variant':variant,'simulations':10000,'forecast':str(fp.relative_to(ROOT))});print(json.dumps({'stage':'simulation_frozen','job':job,'gameId':g['id'],'variant':variant,'cpuSeconds':time.process_time()-before}),flush=True)
            except (ValueError,KeyError,AssertionError) as e:failures.append({'gameId':g['id'],'variant':variant,'error':str(e)});print(json.dumps({'stage':'simulation_failed','job':job,**failures[-1]}),flush=True)
        if forecasts:
            try:
                box=official_box(g,packets);boxes[g['id']]=box
                for variant,f in forecasts.items():freeze_json(folder/'grades'/variant/(g['id'].replace(':','_')+'.json.gz'),mc_grade(f,g,box,predictions))
            except Exception as e:failures.append({'gameId':g['id'],'stage':'official_grading','error':str(e)})
    # Every point forecast in this cohort is already immutable before outcomes.
    for g in games:
        if g['id'] in boxes:continue
        try:boxes[g['id']]=official_box(g,packets)
        except Exception as e:failures.append({'gameId':g['id'],'stage':'point_grading','error':str(e)})
    freeze_json(folder/'point-grades.json.gz',point_grade(predictions,boxes,sport))
    from .evaluation import compare,summarize
    gs={v:{read(path)['gameId']:read(path) for path in (folder/'grades'/v).glob('*.json.gz')} for v in variants};summary={v:summarize(list(rows.values())) for v,rows in gs.items()};comparisons={v:compare(gs['v19_reference'],gs[v],sport) for v in variants if v!='v19_reference'};freeze_json(folder/'metrics.json',{'summaries':summary,'comparisons':comparisons})
    result={'status':'completed','sport':sport,'cohort':cohort,'cpuSeconds':time.process_time(),'activeSeconds':time.monotonic()-start,'projectionGames':len({r['gameId'] for r in predictions}),'officialOutcomes':len(boxes),'runs':runs,'completeGamesSimulated':sum(r['simulations'] for r in runs),'failures':failures,'reservedFinalOpened':False,'productionWrites':0,'experimentOutcomes':[{'variant':v,**d} for v,d in comparisons.items()]};freeze_json(folder/'result.json',result);return result
