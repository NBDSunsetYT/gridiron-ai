"""Seeded NBA-only chronological audit. Frozen forecasts precede final retrieval."""
import argparse,gzip,hashlib,json,math,os,pickle,random,sys,time,urllib.request
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modeling.audit_storage import snapshot_claim,write_snapshot_once
from modeling.nba_v15 import load_nba,fit_nba,simulate_nba,STATS,VERSION
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/engine-v15/nba'
def games():
    p=OUT/'owned-dataset.cache'
    if p.exists():return pickle.load(p.open('rb'))
    d=load_nba('/tmp/gridiron-nba-player_box_2025.parquet','/tmp/gridiron-nba-team_box_2025.parquet','/tmp/gridiron-nba-pbp-2025.parquet');OUT.mkdir(parents=True,exist_ok=True);pickle.dump(d,p.open('wb'));return d
def prepare():
    path=OUT/'selection.json'
    if path.exists():raise ValueError('NBA selection already frozen')
    published=ROOT/'docs/reports/v15-nba-selection.json'
    if published.exists():
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(published.read_bytes());print('Restored the published frozen game selection; no new test sample was selected.');return
    rng=random.Random(15016);data=games();selected=[]
    for phase,n,start,end in [('development',10,'2025-01-01','2025-02-16'),('validation',10,'2025-03-01','2025-04-01'),('test',20,'2025-04-01','2025-05-01')]:
        eligible=[g for g in sorted(data.values(),key=lambda g:g['id']) if start<=g['at'][:10]<end and len(g['teams'])==2 and all(1<=int(t)<=30 for t in g['teams'])]
        rng.shuffle(eligible)
        for g in eligible[:n]:
            at=datetime.fromisoformat(g['at']);cutoff=(at-timedelta(days=at.weekday())).replace(hour=0,minute=0,second=0,microsecond=0).isoformat();selected.append({'id':g['id'],'at':g['at'],'phase':phase,'fitCutoff':cutoff})
    path.write_text(json.dumps({'sport':'NBA','seed':15016,'simulationsPerGame':10000,'games':selected,'prospectiveQualified':0,'reason':'Original pregame publication, injury and starting-lineup snapshots unavailable.'},indent=2));print({'selected':len(selected)},flush=True)
def run_group(group):
    cutoff,selection=group;data=games();source=hashlib.sha256(b''.join(Path('/tmp/gridiron-nba-'+name).read_bytes() for name in ['player_box_2025.parquet','team_box_2025.parquet','pbp-2025.parquet'])).hexdigest();model=fit_nba(data,cutoff,source);results=[]
    folder=OUT/('runs-'+VERSION.rsplit('-',1)[-1]);folder.mkdir(exist_ok=True);modelpath=OUT/('models-'+VERSION.rsplit('-',1)[-1]);modelpath.mkdir(exist_ok=True);artifact=modelpath/(cutoff[:10]+'-'+model['sha256']+'.json.gz')
    if not artifact.exists():artifact.write_bytes(gzip.compress(json.dumps(model,separators=(',',':')).encode(),mtime=0))
    for selected in selection:
        game=data[selected['id'].split(':')[-1]];path=folder/(game['id'].replace(':','_')+'.json.gz');summary=path.with_suffix('.summary.json')
        with snapshot_claim(summary) as acquired:
            if not acquired:continue
            if summary.exists():results.append(json.loads(summary.read_text()));continue
            start=time.process_time()
            try:
                home=next(t for t,r in game['teams'].items() if r['team_home_away']=='home');away=next(t for t in game['teams'] if t!=home)
                result=json.loads(gzip.decompress(path.read_bytes()))['result'] if path.exists() else simulate_nba(model,home,away,game['at'],10000,15016,batch_size=2000)
                if result['inputDataVersion']!=model['sha256']:raise ValueError('Frozen forecast input differs; choose a new versioned audit directory')
                write_snapshot_once(path,gzip.compress(json.dumps({'game':selected,'result':result,'mode':'retrospective','modelCodeSha256':hashlib.sha256((ROOT/'modeling/nba_v15.py').read_bytes()).hexdigest()},separators=(',',':')).encode(),mtime=0))
                # Verify final status and exact team scores independently after freezing.
                actualpath=folder/(game['id'].replace(':','_')+'.actual.json')
                if actualpath.exists():actual=json.loads(actualpath.read_text())
                else:
                    with urllib.request.urlopen('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+game['id'].split(':')[-1],timeout=20) as response:actual=json.load(response)
                    actualpath.write_text(json.dumps({'header':actual['header']},separators=(',',':')))
                h=actual['header'];comp=h['competitions'][0]
                if str(h['id'])!=game['id'].split(':')[-1] or not comp['status']['type']['completed']:raise ValueError('NBA final status not verified')
                observed={str(t['team']['id']):int(t['score']) for t in comp['competitors']}
                if any(observed[t]!=game['teams'][t]['team_score'] for t in (home,away)):raise ValueError('NBA source final scores disagree')
                baseline={};baseplayers={}
                for t in (home,away):
                    history=sorted((g for g in data.values() if t in g['teams'] and g['at']<cutoff),key=lambda g:g['at'])[-10:]
                    baseline[t]=sum(g['teams'][t]['team_score'] for g in history)/len(history)
                    byplayer=defaultdict(lambda:defaultdict(list))
                    for g in history[-5:]:
                        for p in g['players']:
                            if str(p['team_id'])==t:
                                for stat in ['points','rebounds','assists','steals','blocks','turnovers']:byplayer[str(p['athlete_id'])][stat].append(float(p['offensive_rebounds']+p['defensive_rebounds']) if stat=='rebounds' else float(p.get(stat) or 0))
                    baseplayers.update({p:{s:sum(v)/len(v) for s,v in stats.items()} for p,stats in byplayer.items()})
                mapped={'points':'points','assists':'assists','three_point_field_goals_made':'threePointersMade','steals':'steals','blocks':'blocks','turnovers':'turnovers'};pe=[]
                for p in game['players']:
                    pid=str(p['athlete_id']);distributions=result['players'].get('nba:espn:'+pid)
                    if not distributions or not p.get('minutes'):continue
                    stats={dest:float(p[key]) for key,dest in mapped.items()};stats['rebounds']=float(p['offensive_rebounds']+p['defensive_rebounds']);stats.update(pointsReboundsAssists=stats['points']+stats['rebounds']+stats['assists'],pointsRebounds=stats['points']+stats['rebounds'],pointsAssists=stats['points']+stats['assists'],reboundsAssists=stats['rebounds']+stats['assists'])
                    for stat,value in stats.items():
                        dist=distributions[stat];pe.append({'id':'nba:espn:'+pid,'stat':stat,'mean':dist['mean'],'actual':value,'error':dist['mean']-value,'baseline':baseplayers.get(pid,{}).get(stat),'covered90':dist['interval90'][0]<=value<=dist['interval90'][1]})
                p=result['homeWinProbability'];winner=int(observed[home]>observed[away]);errors=[result['scoreDistributions'][t]['mean']-observed[t] for t in (home,away)]
                report={'sport':'NBA','gameId':game['id'],'phase':selected['phase'],'eventStart':game['at'],'fitCutoff':cutoff,'simulations':10000,'seed':15016,'status':'evaluated','scoreErrors':errors,'baselineScoreErrors':[baseline[t]-observed[t] for t in (home,away)],'homeProbability':p,'actualHomeWin':winner,'brier':(p-winner)**2,'logLoss':-math.log(max(1e-15,p if winner else 1-p)),'playerErrors':pe,'finalStatusVerified':True,'quality':result['quality'],'cpuSeconds':time.process_time()-start,'mode':'retrospective','publicationVerified':False,'modelVersion':VERSION}
            except Exception as e:report={'gameId':game['id'],'sport':'NBA','phase':selected['phase'],'status':'unavailable','error':str(e),'cpuSeconds':time.process_time()-start}
            summary.write_text(json.dumps(report,separators=(',',':')));print(json.dumps({k:report.get(k) for k in ['gameId','phase','status','error','cpuSeconds']}),flush=True);results.append(report)
    return results
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--phase',choices=['development','validation','test']);p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    if a.prepare:prepare()
    else:
        rows=json.loads((OUT/'selection.json').read_text())['games'];groups=defaultdict(list)
        for row in rows:
            if row['phase']==a.phase:
                selected=dict(row)
                if a.phase=='test':
                    selected['fitCutoff']='2025-04-01T00:00:00+00:00'
                    selected['testProtocol']='static pre-period fit; no final-period outcomes or roster updates'
                groups[selected['fitCutoff']].append(selected)
        with ProcessPoolExecutor(max_workers=max(1,min(2,a.workers))) as pool:
            for _ in pool.map(run_group,groups.items()):pass
