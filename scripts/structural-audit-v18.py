"""Local causal-limit-aware decomposition of the 342 exposed development games."""
import gzip,json,sys,time,resource,hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.structural_v18.data import packets,archives,stamp
from modeling.structural_v18.models import error_metrics

def load(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def measure(rows):
    if not rows:return None
    e=error_metrics([r['actual'] for r in rows],[r['mean'] for r in rows]);e.update(games=len({r['gameId'] for r in rows}),players=len({r['id'] for r in rows}));b=[r for r in rows if r.get('baseline') is not None]
    if b:e['sameRowsRollingBaseline']={'simulation':error_metrics([r['actual'] for r in b],[r['mean'] for r in b]),'baseline':error_metrics([r['actual'] for r in b],[r['baseline'] for r in b])}
    return e

def main():
    resource.setrlimit(resource.RLIMIT_CPU,(120,122));cpu=time.process_time();started=time.monotonic();rows=[];games=[];sources={}
    legacy=load(ROOT/'docs/reports/development-audit-v17.json')['legacy'];later=load(ROOT/'docs/reports/calibration-v17.json')['leagues']
    packets_by={s:{g['id']:g for g in packets(s)} for s in ['NFL','CFB','NBA']};event_counts={}
    for sport in ['NFL','CFB']:
        counts=defaultdict(int)
        for r in archives(sport)['rows']:
            if r['kind'] in ('pass','sack','rush','kneel','punt','field_goal','penalty'):counts[r['game']]+=1
        event_counts[sport]=counts
    for sport in ['NFL','CFB','NBA']:
        paths=list(legacy[sport]['sourceChecksums'])+[p for p in later[sport]['sourceChecksums'] if '/reference-v15/' in p]
        for p in paths:
            path=ROOT/p;d=load(path);gid=d['gameId'];event=d['eventStart'];sources[p]=hashlib.sha256(path.read_bytes()).hexdigest();homep=d['homeProbability'];ps=d.get('player',d.get('playerErrors',[]));score=d.get('score');score_errors=[r['error'] for r in score] if score else d['scoreErrors'];baseline=d.get('baselineScoreErrors');packet=packets_by[sport].get(gid)
            g={'gameId':gid,'sport':sport,'at':event,'season':packet['season'] if packet else event[:4],'homeProbability':homep,'actualHomeWin':d['actualHomeWin'],'scores':score_errors,'baselineScoreErrors':baseline,'expectedPlays':d.get('tempo',{}).get('plays')}
            if packet:g['actualPlays']=sum(t['totals']['plays'] for t in packet['teams'].values());g['actualModelEvents']=event_counts.get(sport,{}).get(gid)
            games.append(g)
            for r in ps:
                player_id=r['id'].split(':')[-1] if sport=='NBA' else r['id'];team=next((t for t,box in packet['teams'].items() if player_id in box['players']),None) if packet else None
                favorite='unknown' if team is None or homep==.5 else 'favorite' if (homep>.5)==(team==packet['home']) else 'underdog'
                row={**r,'gameId':gid,'sport':sport,'season':g['season'],'injury':'unknown','teamFavorite':favorite,'position':r.get('position','unknown'),'favoriteConfidence':max(homep,1-homep),'volume':float(r.get('baseline') if r.get('baseline') is not None else r['mean'])};rows.append(row)
    report={'developmentGames':len(games),'newSimulations':0,'productionPromotions':[],'sourceChecksums':sources,'leagues':{},'limitations':['342 games were exposed to prior selection and are development only.','No verified historical injury publication archive; injury-stratified causal inference is unavailable.','Legacy forecasts do not carry reliable official positions or team attribution for every player. Unknown is retained.','Model favorite confidence is not a verified market favorite.','Pace proxies and football scrimmage plays are distinguished from exact basketball possessions.','Opportunity/efficiency error decomposition is algebraic and descriptive, not a causal injury diagnosis.']}
    for sport in ['NFL','CFB','NBA']:
        rs=[r for r in rows if r['sport']==sport];gs=[g for g in games if g['sport']==sport];groups={}
        for axis in ['season','position','injury','teamFavorite']:
            groups[axis]={}
            for val in sorted({str(r[axis]) for r in rs}):groups[axis][val]={s:measure([r for r in rs if str(r[axis])==val and r['stat']==s]) for s in sorted({r['stat'] for r in rs})}
        bystat={}
        for stat in sorted({r['stat'] for r in rs}):
            rr=[r for r in rs if r['stat']==stat];med=float(np.median([r['volume'] for r in rr]));bystat[stat]={'all':measure(rr),'nonzeroPregameForecastSupport':measure([r for r in rr if r['mean']!=0 or (r.get('baseline') or 0)!=0]),'volumeSplit':{'cutoff':med,'low':measure([r for r in rr if r['volume']<=med]),'high':measure([r for r in rr if r['volume']>med])},'favoriteConfidence':{'below80':measure([r for r in rr if r['favoriteConfidence']<.8]),'atLeast80':measure([r for r in rr if r['favoriteConfidence']>=.8])}}
        pace=[g['expectedPlays'] for g in gs if g.get('expectedPlays') is not None and g.get('actualPlays') is not None]
        player_groups=defaultdict(lambda:defaultdict(list))
        for r in rs:player_groups[r['id']][r['stat']].append(r)
        root={'games':len(gs),'seasons':sorted({str(g['season']) for g in gs}),'rows':len(rs),'groups':groups,'byStat':bystat,'teamScore':error_metrics([0 for g in gs for e in g['scores']],[e for g in gs for e in g['scores']]),'byPlayer':{p:{s:measure(v) for s,v in stats.items()} for p,stats in player_groups.items()}}

        if pace:
            selected=[g for g in gs if g.get('expectedPlays') is not None and g.get('actualPlays') is not None];root['scrimmagePlayCount']={'n':len(pace),**error_metrics([g['actualPlays'] for g in selected],[g['expectedPlays'] for g in selected]),'definition':'Historical normalized pass/sack/rush/kneel plays; check engine play-count definition before causal attribution.'}
        aligned=[g for g in gs if g.get('expectedPlays') is not None and g.get('actualModelEvents') is not None]
        if aligned:root['alignedStateTransitionEvents']={**error_metrics([g['actualModelEvents'] for g in aligned],[g['expectedPlays'] for g in aligned]),'games':len(aligned),'kinds':['pass','sack','rush','kneel','punt','field_goal','penalty']}
        pace_cutoff=float(np.median(pace)) if pace else None;by_game={g['gameId']:g for g in gs}
        root['expectedPaceBreakdown']={'definition':'Median predicted accepted football transitions, not verified market pace','median':pace_cutoff,'withPaceEvidence':{s:measure([r for r in rs if r['stat']==s and by_game[r['gameId']].get('expectedPlays') is not None]) for s in sorted({r['stat'] for r in rs})},'belowMedian':{s:measure([r for r in rs if r['stat']==s and by_game[r['gameId']].get('expectedPlays') is not None and by_game[r['gameId']]['expectedPlays']<=pace_cutoff]) for s in sorted({r['stat'] for r in rs})} if pace else {},'aboveMedian':{s:measure([r for r in rs if r['stat']==s and by_game[r['gameId']].get('expectedPlays') is not None and by_game[r['gameId']]['expectedPlays']>pace_cutoff]) for s in sorted({r['stat'] for r in rs})} if pace else {}}
        report['leagues'][sport]=root
    # Independent NBA complete-box coverage/rotation diagnostic on 24 later games.
    models={}
    for p in (ROOT/'artifacts/learning-v16/models').glob('*.json.gz'):
        m=load(p)
        if m.get('sport')=='NBA':models[m['sha256']]=m
    raw=archives('NBA');flat=packets_by['NBA'];rotation=[];decomposition=defaultdict(list);minute_rows=[];unmodeled=0
    selection=load(ROOT/'artifacts/learning-v16/protocol.json')['selection']
    for game in [g for g in selection if g['sport']=='NBA' and g['phase']=='validation']:
        path=ROOT/'artifacts/learning-v16/runs/reference-v15/NBA'/(game['id'].replace(':','_')+'.forecast.json.gz');f=load(path)['forecast'];m=models.get(f['inputDataVersion']);packet=flat.get(game['id'])
        if not packet:continue
        actual={p:ps for t in packet['teams'].values() for p,ps in t['players'].items()}
        for tid,r in f['rotationAssumptions'].items():
            if not m:continue
            hs=m['teams'].get(tid,[]);valid=[g for g in flat.values() if tid in g['teams'] and stamp(g['at'])+6*3600<stamp(m['cutoff'])]
            latest=max((g['at'] for g in hs),default=None);latest_box=max((g['at'] for g in valid),default=None)
            if latest and latest_box:rotation.append({'gameId':game['id'],'team':tid,'lastPaceQualified':latest,'lastValidBox':latest_box,'daysLost':(stamp(latest_box)-stamp(latest))/86400,'daysSinceRotation':(stamp(f['eventStart'])-stamp(latest))/86400})
        for pid,ds in f['players'].items():
            p=pid.split(':')[-1];a=actual.get(p);actual_minutes=a['stats']['minutes'] if a else 0.;pred_minutes=ds['minutes']['mean'];minute_rows.append({'id':pid,'gameId':game['id'],'mean':pred_minutes,'actual':actual_minutes,'baseline':None})
            if pred_minutes>0 and actual_minutes>0:
                for stat in ('points','rebounds','assists'):
                    pred=ds[stat]['mean'];observed=a['stats'][stat];ep=pred/pred_minutes;ea=observed/actual_minutes;op=(pred_minutes-actual_minutes)*(ep+ea)/2;eff=(ep-ea)*(pred_minutes+actual_minutes)/2
                    if abs(op+eff-(pred-observed))>1e-6:raise ValueError('Error decomposition does not reconcile')
                    decomposition[stat].append({'opportunityComponent':op,'efficiencyComponent':eff,'error':pred-observed})
        unmodeled+=sum('nba:espn:'+p not in f['players'] for p in actual)
    # Inspect source acceptance without substituting a possession coefficient.
    counts=defaultdict(int)
    for g in raw.values():
        for tid,t in g['teams'].items():
            roster=[p for p in g['players'] if str(p['team_id'])==str(tid) and float(p.get('minutes') or 0)>0];mins=sum(float(p['minutes']) for p in roster)
            if len(roster)<5 or not 235<=mins<=400 or sum(p['points'] for p in roster)!=t['team_score']:continue
            counts['validCompleteBoxes']+=1;tr=g.get('freeThrowTrips',{}).get(tid,[])
            counts['droppedForTrips']+=int(bool(t['free_throws_attempted']) and (not tr or sum(tr)!=t['free_throws_attempted']))
    report['nbaStructuralEvidence']={'sourceCoverage':dict(counts),'rotationComparisons':rotation,'averageDaysLost':float(np.mean([r['daysLost'] for r in rotation])) if rotation else None,'maximumDaysLost':max([r['daysLost'] for r in rotation],default=None),'minutesIncludingForecastNonparticipants':measure(minute_rows),'unmodeledActualParticipants':unmodeled,'descriptiveDecomposition':{s:{'observations':len(v),'meanAbsoluteOpportunityComponent':float(np.mean([abs(r['opportunityComponent']) for r in v])),'meanAbsoluteEfficiencyComponent':float(np.mean([abs(r['efficiencyComponent']) for r in v])),'signedOpportunityBias':float(np.mean([r['opportunityComponent'] for r in v])),'signedEfficiencyBias':float(np.mean([r['efficiencyComponent'] for r in v]))} for s,v in decomposition.items()}}
    report['resources']={'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-started,'hostingCpuSeconds':0,'providerRequests':0}
    path=ROOT/'artifacts/structural-v18/root-causes-v3.json.gz';path.write_bytes(gzip.compress(json.dumps(report,sort_keys=True,allow_nan=False).encode(),mtime=0));summary={**report,'leagues':{s:{k:v for k,v in r.items() if k!='byPlayer'} for s,r in report['leagues'].items()}};(ROOT/'docs/reports/structural-v18-root-causes-v3.json').write_text(json.dumps(summary,sort_keys=True,indent=2,allow_nan=False)+'\n');print(json.dumps({'games':len(games),'nbaEvidence':report['nbaStructuralEvidence'],'resources':report['resources']}))
if __name__=='__main__':main()
