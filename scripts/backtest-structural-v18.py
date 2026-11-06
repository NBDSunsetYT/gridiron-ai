"""Budgeted LOCAL full-game comparison. Writes predictions before grading finals.
Exactly the preregistered first three selected IDs in each chronological window.
No training on validation outcomes, no provider/DB writes, no production imports.
"""
import argparse,copy,gzip,hashlib,json,os,pickle,resource,sys,time,importlib.util
from pathlib import Path
from datetime import datetime,timedelta
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.structural_v18.data import archives,packets,stamp
from modeling.structural_v18 import nba as structural,football as structural_football
from modeling import nba_v15,football_v15
from modeling.iterative_learning import digest,unrealism_flags,distribution_errors
from modeling.reproducibility import derive_draw_order
from modeling.calibration_research import metrics,paired_interval
spec=importlib.util.spec_from_file_location('structural_runner',ROOT/'scripts/structural-v18.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
OUT=runner.OUT

def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def evaluate(f,packet):
    # Only after the forecast has been frozen to disk.
    home,away=f['home'],f['away'];actual={t:v['totals']['score'] for t,v in packet['teams'].items()};players={p:v for t in packet['teams'].values() for p,v in t['players'].items()};rows=[]
    for pid,stats in f['players'].items():
        p=pid.split(':')[-1] if f['sport']=='NBA' else pid;obs=players.get(p)
        # A complete, reconciled NBA box supports a zero DNP outcome. Football
        # partial participant logs do not; missing football identity is excluded.
        if not obs and f['sport']!='NBA':continue
        for stat,d in stats.items():
            if obs and stat not in obs['stats']:continue
            y=obs['stats'][stat] if obs else 0.;e=distribution_errors(d,y);rows.append({'id':pid,'stat':stat,**e})
    truth=int(actual[home]>actual[away]);p=f['homeWinProbability'];scores=[distribution_errors(f['scoreDistributions'][t],actual[t]) for t in (home,away)]
    return {'gameId':packet['id'],'sport':f['sport'],'candidate':f['modelVersion'],'probability':p,'truth':truth,'score':scores,'players':rows,'forecastPlayers':len(f['players']),'unmodeledActualParticipants':sum(('nba:espn:'+pid if f['sport']=='NBA' else pid) not in f['players'] for pid in players),'ties':actual[home]==actual[away]}

def main():
    p=argparse.ArgumentParser();p.add_argument('--sport',choices=['NBA','NFL','CFB'],required=True);p.add_argument('--cpu-seconds',type=int,default=500);a=p.parse_args()
    if os.environ.get('VERCEL') or os.environ.get('RENDER'):p.error('Local research only')
    if not 1<=a.cpu_seconds<=600:p.error('Bounded local CPU budget 1..600')
    resource.setrlimit(resource.RLIMIT_CPU,(a.cpu_seconds,a.cpu_seconds+2));started=time.monotonic();cpu=time.process_time();sport=a.sport;protocol=read(OUT/'protocol.json');runner.verify_sources(protocol);selected=[]
    for i in range(3):selected.extend([g for g in protocol['selection'][sport] if g['cohort']==i][:protocol['fullGameSubsetPerWindow']])
    data=archives(sport);opportunities={};games={g['id']:g for g in packets(sport)};predicted_minutes={}
    if sport=='NBA':
        for r in read(OUT/'projections/NBA.json.gz')['rows']:
            if r['stat']=='minutes' and r['player']!='__team__':predicted_minutes.setdefault(r['gameId'],{}).setdefault(r['team'],{})[r['player']]=r['predictions']['ridge']
    if sport!='NBA':
        for r in read(OUT/'projections'/(sport+'.json.gz'))['rows']:
            opportunities.setdefault(r['gameId'],{}).setdefault(r['team'],{}).setdefault(r['player'],{})[r['stat']]=r['predictions']['ridge']
    results=defaultdict(list);failures=[];count=0;fits=0;source_files={}
    for cohort in range(3):
        cohort_games=[g for g in selected if g['cohort']==cohort]
        if not cohort_games:continue
        cutoff=(datetime.fromisoformat(min(g['at'] for g in cohort_games).replace('Z','+00:00'))-timedelta(hours=6,seconds=1)).isoformat()
        if sport=='NBA':
            models={'frozen_v15':nba_v15.fit_nba(data,cutoff,'owned-box-and-trip-archives'), 'box_coverage':structural.fit_nba(data,cutoff,'owned-box-and-trip-archives')};fits+=2
        else:
            # The frozen reference algorithm is fitted separately by league.
            # The current repaired normalizer is used; originals stay unchanged.
            rows=[r for r in data['rows'] if r['at']<cutoff];models={'frozen_v15':football_v15.fit_football(rows,sport,cutoff,'owned-repaired-archive')};fits+=1
        for g in cohort_games:
            candidates=['frozen_v15','box_coverage','learned_minutes'] if sport=='NBA' else ['frozen_v15','learned_allocation']
            for candidate in candidates:
                if time.process_time()-cpu>a.cpu_seconds-15:failures.append({'gameId':g['id'],'candidate':candidate,'error':'CPU budget exhausted before next complete run'});continue
                base=OUT/'full-games'/sport/candidate/g['id'].replace(':','_');fp=base.with_suffix('.forecast.json.gz');ep=base.with_suffix('.evaluation.json.gz')
                try:
                    if fp.exists():f=read(fp)['forecast']
                    else:
                        m=copy.deepcopy(models['box_coverage' if candidate=='learned_minutes' else 'frozen_v15' if candidate=='learned_allocation' else candidate])
                        if candidate=='learned_minutes':
                            m.update(variant='learned_minutes',projectedMinutes=predicted_minutes[g['id']]);m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'})
                        if candidate=='learned_allocation':
                            m.update(version=structural_football.VERSION,projectedOpportunities=opportunities[g['id']],dropbackLogitShift={})
                            from scipy.special import logit
                            for t in (g['home'],g['away']):
                                hs=sorted(m['histories'][t].values(),key=lambda h:h['at'])[-3:];old_pass=sum(sum(h['qb'].values()) for h in hs);old_run=sum(sum(h['runner'].values()) for h in hs);projected=opportunities[g['id']][t]['__team__'];new_pass=projected['dropbacks'];new_run=max(0.,projected['plays']-new_pass)
                                if min(old_pass,old_run,new_pass,new_run)<=0:raise ValueError('Unsupported team opportunity budget')
                                m['dropbackLogitShift'][t]=float(logit(new_pass/(new_pass+new_run))-logit(old_pass/(old_pass+old_run)))
                            m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'})
                        runner.save(OUT/'full-models'/(m['sha256']+'.json.gz'),m)
                        if sport!='NBA':runner.save(OUT/'full-models'/(m['sha256']+'.order.json.gz'),derive_draw_order(m,rows))
                        engine=nba_v15 if sport=='NBA' and candidate=='frozen_v15' else structural if sport=='NBA' else structural_football if candidate=='learned_allocation' else football_v15
                        start=time.process_time();kwargs={'representative_games':0} if sport!='NBA' else {}
                        f=engine.simulate_nba(m,g['home'],g['away'],g['at'],10000,18018+cohort,**kwargs) if sport=='NBA' else engine.simulate_football(m,g['home'],g['away'],g['at'],10000,18018+cohort,**kwargs)
                        if unrealism_flags(f):raise ValueError('Internal simulation audit: '+str(unrealism_flags(f)))
                        runner.save(fp,{'game':g,'candidate':candidate,'forecast':f,'protocolSha256':runner.digest(OUT/'protocol.json'),'cpuSeconds':time.process_time()-start,'pregamePublicationVerified':False,'dependencies':{k:__import__(k).__version__ for k in ['numpy','scipy','sklearn']}});count+=1
                    source_files[str(fp.relative_to(ROOT))]=runner.digest(fp)
                    result=evaluate(f,games[g['id']]);result['candidate']=candidate;runner.save(ep,result);results[candidate].append(result)
                    print(json.dumps({'sport':sport,'game':g['id'],'candidate':candidate,'status':'complete','cpuSeconds':time.process_time()-cpu}),flush=True)
                except (ValueError,AssertionError,KeyError) as e:failures.append({'gameId':g['id'],'candidate':candidate,'error':str(e)});print(json.dumps(failures[-1]),flush=True)
    report={'sport':sport,'games':len({r['gameId'] for rs in results.values() for r in rs}),'candidates':{},'failures':failures,'sourceChecksums':source_files,'promoted':[],'finalTestOpened':False}
    for candidate,rs in results.items():
        categories=defaultdict(list)
        for r in rs:
            for row in r['players']:categories[row['stat']].append((r['gameId'],row))
        summary={'games':len(rs),'moneyline':metrics([r['probability'] for r in rs if not r['ties']],[r['truth'] for r in rs if not r['ties']]),'teamScore':runner.error_metrics([v['actual'] for r in rs for v in r['score']],[v['mean'] for r in rs for v in r['score']]),'unmodeledActualParticipants':sum(r['unmodeledActualParticipants'] for r in rs),'byStat':{s:{**runner.error_metrics([p['actual'] for _,p in v],[p['mean'] for _,p in v]),'games':len({g for g,p in v}),'players':len({p['id'] for g,p in v}),'interval90Coverage':float(np.mean([p['coverage']['0.9']['covered'] for g,p in v]))} for s,v in categories.items()}}
        ref={r['gameId']:r for r in results['frozen_v15']};pairs=[(ref[r['gameId']],r) for r in rs if r['gameId'] in ref]
        summary['pairedScoreMAE']=paired_interval([np.mean([abs(p['error']) for p in b['score']]) for b,c in pairs],[np.mean([abs(p['error']) for p in c['score']]) for b,c in pairs])
        report['candidates'][candidate]=summary
    report['resources']={'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-started,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'fits':fits,'newRuns':count,'completeGamesSimulated':10000*count,'hostingCpuSeconds':0};runner.save(OUT/(sport+'-full-game-report.json'),report);print(json.dumps({'sport':sport,'resources':report['resources'],'failures':failures}),flush=True)
if __name__=='__main__':main()
