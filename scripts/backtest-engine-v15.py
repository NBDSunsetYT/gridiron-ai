"""Resource-bounded, seeded chronological research audit, never auto-promotes.

Run --prepare once, then --phase development/validation/test. Test games are
frozen before evaluation and known diagnostic games are quarantined. Every
forecast is saved before its final-stat retrieval. Current source corrections
and missing original injury/lineup archives prevent a prospective-accuracy claim.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import pickle
import random
import sys
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime,timezone,timedelta
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modeling.audit_storage import snapshot_claim,write_snapshot_once
from modeling.football_data_v15 import load_football,training_before,NORMALIZER_VERSION
from modeling.football_v15 import fit_football,simulate_football,VERSION

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/engine-v15'
BASE=OUT
QUARANTINE={'cfb:espn:401858509','cfb:espn:401756926','2025_07_LA_JAX','2025_13_KC_DAL'}


def cached_json(url,path):
    if path.exists():return json.loads(path.read_text())
    req=urllib.request.Request(url,headers={'User-Agent':'GRIDIRON-AI-Historical-Audit/15','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as r:raw=r.read(8_000_001)
    if len(raw)>8_000_000:raise ValueError('Historical response exceeds bound')
    value=json.loads(raw);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);return value


def dataset(sport):
    dest=OUT/(sport+'-'+NORMALIZER_VERSION+'.cache')
    if dest.exists():return pickle.load(dest.open('rb')) # owned local disposable cache, never accepts uploads
    merged={'sport':sport,'games':{},'rows':[],'sources':[]}
    for year in (2024,2025):
        path=Path('/tmp/gridiron-'+('cfb-public-pbp-' if sport=='CFB' else 'nfl-pbp-')+str(year)+'.parquet')
        data=load_football(path,sport);merged['rows'].extend(data['rows']);merged['games'].update(data['games']);merged['sources'].append({'year':year,'sha256':data['sourceSha256'],'rejections':data['rejected']})
    OUT.mkdir(parents=True,exist_ok=True);pickle.dump(merged,dest.open('wb'));return merged


def prepare():
    manifest=OUT/'selection.json'
    if manifest.exists():raise ValueError('Selection already frozen; use it rather than silently choosing new test games')
    published=ROOT/'docs/reports/v15-football-selection.json'
    if published.exists():
        manifest.parent.mkdir(parents=True,exist_ok=True);manifest.write_bytes(published.read_bytes());print('Restored the published frozen game selection; no new test sample was selected.');return
    # Existing published diagnostics are not untouched evidence.
    def ids(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k in ('gameId','game_id') and isinstance(v,str):QUARANTINE.add(v)
                else:ids(v)
        elif isinstance(value,list):
            for v in value:ids(v)
    for file in (ROOT/'docs/reports').glob('*.json'):
        try:ids(json.loads(file.read_text()))
        except (ValueError,OSError):pass
    selected=[];exclusions=[];rng=random.Random(15015)
    targets={'NFL':{'development':100,'validation':50,'test':50},'CFB':{'development':150,'validation':50,'test':100}}
    for sport in ('NFL','CFB'):
        data=dataset(sport)
        for phase,n in targets[sport].items():
            eligible=[]
            for g in sorted(data['games'].values(),key=lambda g:g['id']):
                date=g['firstObservedAt'][:10]
                within=('2024-10-01'<=date<'2025-01-01') if phase=='development' else ('2025-10-01'<=date<'2025-11-15') if phase=='validation' else ('2025-11-15'<=date<'2026-01-01')
                if not within or g['id'] in QUARANTINE or g['plays']<50:continue
                week=datetime.fromisoformat(g['firstObservedAt']);cutoff=(week-timedelta(days=week.weekday())).replace(hour=0,minute=0,second=0,microsecond=0).isoformat()
                history=[p for p in data['games'].values() if p['lastObservedAt']<cutoff]
                if any(sum(t in (p['home'],p['away']) for p in history)<3 for t in (g['home'],g['away'])):continue
                eligible.append({k:g[k] for k in ['id','sport','season','home','away','firstObservedAt','lastObservedAt'] }|{'phase':phase,'fitCutoff':cutoff})
            rng.shuffle(eligible);selected.extend(eligible[:n]);exclusions.append({'sport':sport,'phase':phase,'requested':n,'eligible':len(eligible),'selected':min(n,len(eligible))})
    manifest.write_text(json.dumps({'protocol':'event-chronological-retrospective-15.0.0','seed':15015,'simulationsPerGame':10000,'selection':selected,'coverage':exclusions,'quarantine':sorted(QUARANTINE),'originalPublicationVerified':False,'strictPregameQualifiedGames':0,'reason':'Historical source publication/correction and full pregame lineup/injury snapshots are not verified.','selectionCreatedAt':datetime.now(timezone.utc).isoformat()},indent=2))
    print(json.dumps({'selected':len(selected),'coverage':exclusions}),flush=True)


def final_stats(game):
    sport=game['sport'];gid=game['id'];folder=OUT/'actuals';folder.mkdir(exist_ok=True)
    if sport=='CFB':
        raw=cached_json('https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event='+gid.split(':')[-1],folder/(gid.replace(':','_')+'.json'))
        h=raw.get('header',{});c=h.get('competitions',[{}])[0]
        if str(h.get('id'))!=gid.split(':')[-1] or not c.get('status',{}).get('type',{}).get('completed'):raise ValueError('Final CFB identity/status unavailable')
        players={};scores={}
        for comp in c['competitors']:
            tid='cfb:espn:'+str(comp['team']['id']);scores[tid]=int(comp['score'])
        if set(scores)!={game['home'],game['away']}:raise ValueError('Final CFB team mismatch')
        mapping={'passing':{'YDS':'passingYards','TD':'passingTouchdowns','INT':'interceptions'},'rushing':{'CAR':'carries','YDS':'rushingYards','TD':'rushingTouchdowns'},'receiving':{'REC':'receptions','YDS':'receivingYards','TD':'receivingTouchdowns','TGTS':'targets'}}
        for team in raw.get('boxscore',{}).get('players',[]):
            tid='cfb:espn:'+str(team['team']['id'])
            if tid not in scores:raise ValueError('Unexpected final CFB player team')
            for group in team.get('statistics',[]):
                if group['name'] not in mapping:continue
                for entry in group.get('athletes',[]):
                    pid=str(entry['athlete']['id'])
                    if not pid.isdigit():continue
                    p=players.setdefault('cfb:espn:'+pid,{'name':entry['athlete']['displayName'],'team':tid,'stats':{}})
                    if p['team']!=tid:raise ValueError('Ambiguous final CFB player identity')
                    values=dict(zip(group['labels'],entry['stats']))
                    for label,stat in mapping[group['name']].items():
                        if label in values:p['stats'][stat]=float(values[label])
                    if group['name']=='passing' and 'C/ATT' in values:
                        comp,attempt=values['C/ATT'].split('/');p['stats']['completions']=int(comp);p['stats']['passingAttempts']=int(attempt)
        return scores,players,'ESPN final box score'
    path=folder/('nfl-'+str(game['season'])+'.csv.gz')
    if not path.exists():
        url='https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_'+str(game['season'])+'.csv.gz'
        with urllib.request.urlopen(url,timeout=30) as r:path.write_bytes(r.read(12_000_000))
    mapping={'attempts':'passingAttempts','completions':'completions','passing_yards':'passingYards','passing_tds':'passingTouchdowns','passing_interceptions':'interceptions','carries':'carries','rushing_yards':'rushingYards','rushing_tds':'rushingTouchdowns','receptions':'receptions','receiving_yards':'receivingYards','receiving_tds':'receivingTouchdowns','targets':'targets'}
    players={}
    with gzip.open(path,'rt') as f:
        for row in csv.DictReader(f):
            if row.get('game_id')!=gid:continue
            team=row.get('team');team={'LAR':'LA','JAC':'JAX'}.get(team,team)
            if team not in (game['home'],game['away']):continue
            stats={dest:float(row[src]) for src,dest in mapping.items() if row.get(src) not in ('',None,'NA')}
            if not any(stats.get(k,0)>0 for k in ('passingAttempts','carries','targets','receptions')):continue
            pid=row['player_id']
            if pid in players:raise ValueError('Duplicate NFL final player')
            players[pid]={'name':row.get('player_display_name') or pid,'team':team,'stats':stats}
    if not players:raise ValueError('Published NFL final player rows unavailable')
    # Final score metadata was separated from the fitted play rows by loader.
    data=dataset(sport);g=data['games'][gid]
    return {g['home']:g['actualHome'],g['away']:g['actualAway']},players,'nflverse final player statistics and schedule'


def baseline(data,game):
    cutoff=game['fitCutoff'];history=sorted((g for g in data['games'].values() if g['lastObservedAt']<cutoff),key=lambda g:g['firstObservedAt']);teams={}
    for t in (game['home'],game['away']):
        last=[g for g in history if t in (g['home'],g['away'])][-3:]
        points=[g['actualHome'] if g['home']==t else g['actualAway'] for g in last];allowed=[g['actualAway'] if g['home']==t else g['actualHome'] for g in last]
        players=defaultdict(lambda:defaultdict(list))
        for g in last:
            for pid,p in g['players'].items():
                if p['team']==t:
                    for stat,v in p['stats'].items():players[pid][stat].append(v)
        teams[t]={'points':sum(points)/len(points),'allowed':sum(allowed)/len(allowed),'players':{pid:{s:sum(v)/len(v) for s,v in ss.items()} for pid,ss in players.items()}}
    home,away=game['home'],game['away']
    return {'home':(teams[home]['points']+teams[away]['allowed'])/2,'away':(teams[away]['points']+teams[home]['allowed'])/2,'players':{**teams[home]['players'],**teams[away]['players']}}


def run_group(group):
    sport,cutoff,games,candidate=group
    if candidate=='hurdle':from modeling.football_v15 import fit_football,simulate_football
    else:from modeling.football_v15_baseline import fit_football,simulate_football
    out=BASE/('candidate-hurdle' if candidate=='hurdle' else '')
    out.mkdir(parents=True,exist_ok=True)
    data=dataset(sport);rows=training_before(data,cutoff);rows=[r for r in rows if r['at'][:4]>=str(int(cutoff[:4])-1)]
    source=hashlib.sha256(json.dumps([data['sources'],NORMALIZER_VERSION,cutoff],sort_keys=True).encode()).hexdigest();model=fit_football(rows,sport,cutoff,source)
    modelpath=out/'models'/(sport+'-'+cutoff[:10]+'-'+model['sha256']+'.json.gz');modelpath.parent.mkdir(exist_ok=True)
    if not modelpath.exists():modelpath.write_bytes(gzip.compress(json.dumps(model,separators=(',',':')).encode(),mtime=0))
    results=[]
    for game in games:
        target=out/'runs'/(game['id'].replace(':','_')+'.json.gz');summary=target.with_suffix('.summary.json');target.parent.mkdir(exist_ok=True)
        with snapshot_claim(summary) as acquired:
            if not acquired:continue
            if summary.exists():results.append(json.loads(summary.read_text()));continue
            start=time.process_time()
            try:
                assert game['id'] not in model['trainingGameIds']
                forecast=json.loads(gzip.decompress(target.read_bytes()))['result'] if target.exists() else simulate_football(model,game['home'],game['away'],game['firstObservedAt'],10000,15015,batch_size=2000,representative_games=0)
                if forecast['inputDataVersion']!=model['sha256']:raise ValueError('Frozen forecast input differs; choose a new versioned audit directory')
                # Freeze first, then retrieve actuals. No final input enters model.
                codefile='football_v15.py' if candidate=='hurdle' else 'football_v15_baseline.py'
                write_snapshot_once(target,gzip.compress(json.dumps({'game':game,'result':forecast,'mode':'retrospective','modelCodeSha256':hashlib.sha256((ROOT/'modeling'/codefile).read_bytes()).hexdigest()},separators=(',',':')).encode(),mtime=0))
                scores,actuals,actualsource=final_stats(game);base=baseline(data,game);players=[]
                for pid,stats in forecast['players'].items():
                    observed=actuals.get(pid)
                    if not observed:continue
                    for stat,dist in stats.items():
                        actual=observed['stats'].get(stat)
                        if actual is None or dist['mean']==0 and actual==0:continue
                        b=base['players'].get(pid,{}).get(stat)
                        players.append({'id':pid,'stat':stat,'mean':dist['mean'],'actual':actual,'error':dist['mean']-actual,'baseline':b,'covered90':dist['interval90'][0]<=actual<=dist['interval90'][1]})
                p=forecast['homeWinProbability'];actual=int(scores[game['home']]>scores[game['away']]);pred=[forecast['scoreDistributions'][game[s]]['mean'] for s in ('home','away')];observed=[scores[game[s]] for s in ('home','away')]
                result={'gameId':game['id'],'sport':sport,'phase':game['phase'],'eventStart':game['firstObservedAt'],'fitCutoff':cutoff,'inputVersion':model['sha256'],'simulations':10000,'seed':15015,'homeProbability':p,'actualHomeWin':actual,'brier':(p-actual)**2,'logLoss':-math.log(max(1e-15,p if actual else 1-p)),
                    'predictedScore':pred,'actualScore':observed,'scoreErrors':[pred[i]-observed[i] for i in (0,1)],'baselineScoreErrors':[base[s]-observed[i] for i,s in enumerate(('home','away'))],
                    'playerErrors':players,'tempo':forecast['gameEnvironment'],'actualSource':actualsource,'cpuSeconds':time.process_time()-start,'mode':'retrospective','publicationVerified':False,'status':'evaluated','quality':forecast['quality'],'modelVersion':forecast['modelVersion'],'candidate':candidate}
            except Exception as e:result={'gameId':game['id'],'sport':sport,'phase':game['phase'],'status':'unavailable','error':str(e),'cpuSeconds':time.process_time()-start}
            summary.write_text(json.dumps(result,separators=(',',':')));results.append(result);print(json.dumps({k:result.get(k) for k in ['gameId','sport','phase','status','cpuSeconds','error']}),flush=True)
    return results


def run(phase,workers,limit,candidate):
    manifest=json.loads((OUT/'selection.json').read_text());selected=[g for g in manifest['selection'] if g['phase']==phase]
    if limit:selected=[g for sport in ['NFL','CFB'] for g in [p for p in selected if p['sport']==sport][:max(1,limit//2)]]
    groups=defaultdict(list)
    for original in selected:
        game=dict(original)
        if phase=='test':
            # Freeze all parameters AND roster features before the untouched
            # final period. No earlier test result enters a later test fit.
            game['fitCutoff']='2025-11-15T00:00:00+00:00'
            game['testProtocol']='static pre-period fit; no final-period outcomes or roster updates'
        groups[(game['sport'],game['fitCutoff'])].append(game)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for _ in pool.map(run_group,[(sport,cutoff,games,candidate) for (sport,cutoff),games in groups.items()]):pass


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--phase',choices=['development','validation','test']);p.add_argument('--workers',type=int,default=3);p.add_argument('--limit',type=int);p.add_argument('--candidate',choices=['baseline','hurdle'],default='baseline');a=p.parse_args()
    if a.prepare:prepare()
    elif a.phase:run(a.phase,max(1,min(4,a.workers)),a.limit,a.candidate)
    else:p.error('Choose --prepare or --phase')
