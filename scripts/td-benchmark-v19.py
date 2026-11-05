"""Repaired-label Gamma-Poisson touchdown benchmark for BOTH football leagues.
Not full-game MC, not calibrated, not a wager/settlement model. Population priors
train before July 2025; player posteriors use only earlier completed games.
"""
import sys,json,gzip,time,math
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import nbinom
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.structural_v18.data import archives,stamp
from modeling.iterative_learning import freeze_json
from modeling.reconstruction_v19.outcomes import player_outcome
from modeling.reconstruction_v19.runtime import local_only
from modeling.structural_v18.models import error_metrics,cluster_delta
from modeling.calibration_research import metrics
OUT=ROOT/'artifacts/parallel-v19';local_only();cpu=time.process_time();protocol=json.load((OUT/'protocol.json').open());report={};stat_op={'passingTouchdowns':'passingAttempts','receivingTouchdowns':'receptions','rushingTouchdowns':'carries'}
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
for sport in ['NFL','CFB']:
    data=archives(sport);td=read(OUT/'repaired-labels'/(sport+'-td-flags.json.gz'))['games'];projections=read(OUT/'projections'/(sport+'.json.gz'))['rows'];project={(r['gameId'],r['team'],r['player'],r['stat']):r['predictions']['ridge'] for r in projections};by_team=defaultdict(list)
    for g in sorted(data['games'].values(),key=lambda g:g['lastObservedAt']):
        for t in (g['home'],g['away']):by_team[t].append(g)
    priors={}
    for stat,op in stat_op.items():
        grouped=defaultdict(lambda:np.zeros(2))
        for gid,g in data['games'].items():
            if g['lastObservedAt']>=protocol['projectionTrainingCutoff'] or gid not in td or not td[gid]['supported'][stat]:continue
            for pid,p in g['players'].items():
                exposure=p['stats'].get(op)
                if exposure is None or exposure<=0:continue
                grouped[pid]+=np.array([td[gid]['players'].get(pid,{}).get(stat,0),exposure])
        rows=np.array(list(grouped.values()));k,n=rows[:,0],rows[:,1]
        if len(rows)<30 or k.sum()==0:raise ValueError('Corrected touchdown prior lacks sufficient evidence')
        def loss(z):
            a,b=np.exp(z);return -float(np.sum(gammaln(a+k)-gammaln(a)+a*np.log(b)-(a+k)*np.log(b+n)))
        fit=minimize(loss,np.log([.5,10]),method='L-BFGS-B',bounds=[(-7,14),(-7,14)])
        if not fit.success:raise ValueError('Gamma-Poisson prior did not converge')
        priors[stat]={'shape':float(np.exp(fit.x[0])),'rate':float(np.exp(fit.x[1])),'players':len(rows),'touchdowns':int(k.sum()),'opportunities':float(n.sum()),'trainingEnd':protocol['projectionTrainingCutoff']}
    predictions=[];grades=[]
    for event in protocol['selection'][sport]:
        file=OUT/'outcomes'/(event['id'].replace(':','_')+'.official.json.gz')
        if not file.exists():continue
        box=read(file)['box']
        for team in (event['home'],event['away']):
          earlier=[g for g in by_team[team] if stamp(g['lastObservedAt'])+6*3600<stamp(event['at'])]
          for stat,op in stat_op.items():
            player_ids={r['player'] for r in projections if r['gameId']==event['id'] and r['team']==team and r['stat']==op and r['player']!='__team__'}
            for pid in sorted(player_ids):
                mu=project[(event['id'],team,pid,op)];k=n=0.;history=[]
                for g in earlier:
                    gid=g['id']
                    if gid not in td or not td[gid]['supported'][stat]:continue
                    count=td[gid]['players'].get(pid,{}).get(stat,0);exposure=g['players'].get(pid,{}).get('stats',{}).get(op,0);k+=count;n+=exposure;history.append(count)
                prior=priors[stat];a=prior['shape']+k;b=prior['rate']+n;p=b/(b+mu) if mu else 1.;mean=mu*a/b;prob=1-p**a;baseline=float(np.mean(history[-5:])) if history else 0.;pred={'sport':sport,'gameId':event['id'],'team':team,'playerId':pid,'stat':stat,'mean':mean,'probabilityAtLeastOne':prob,'interval90':[float(nbinom.ppf(.05,a,p)),float(nbinom.ppf(.95,a,p))],'model':'gamma_poisson_opportunity_count_19.0.0','predictedOpportunity':mu,'pastTouchdowns':k,'pastOpportunities':n,'calibrated':False,'monteCarloTrials':None,'rolling5Baseline':baseline,'informationCutoff':event['at'],'assumptions':'Poisson events per predicted opportunity with Gamma player-rate pooling. Standalone count benchmark, not a coherent game simulation or a bounded Bernoulli-per-attempt model.'};predictions.append(pred)
                y,reason=player_outcome(box,pid,team,stat)
                if y is not None:grades.append({**pred,'actual':y,'zeroMeaning':reason,'outcome':int(y>=1)})
    freeze_json(OUT/'td-benchmark'/(sport+'.predictions.json.gz'),{'priors':priors,'predictions':predictions});freeze_json(OUT/'td-benchmark'/(sport+'.grades.json.gz'),grades);groups={}
    for stat in stat_op:
        rs=[r for r in grades if r['stat']==stat]
        if not rs:continue
        groups[stat]={**error_metrics([r['actual'] for r in rs],[r['mean'] for r in rs]),'games':len({r['gameId'] for r in rs}),'players':len({r['playerId'] for r in rs}),'rolling5':error_metrics([r['actual'] for r in rs],[r['rolling5Baseline'] for r in rs]),'probabilityAtLeastOne':metrics([r['probabilityAtLeastOne'] for r in rs],[r['outcome'] for r in rs]),'interval90Coverage':float(np.mean([r['interval90'][0]<=r['actual']<=r['interval90'][1] for r in rs])),'pairedMAE':cluster_delta([{'gameId':r['gameId'],'y':r['actual']} for r in rs],[r['rolling5Baseline'] for r in rs],[r['mean'] for r in rs])}
    report[sport]={'priors':priors,'groups':groups,'legacyZeroTDHeadsWithdrawn':True,'promoted':False};print(json.dumps({'sport':sport,'games':len({r['gameId'] for r in grades}),'gradedPlayerStatistics':len(grades),'cpuSeconds':time.process_time()-cpu}),flush=True)
freeze_json(ROOT/'docs/reports/parallel-v19-td-benchmark.json',{'leagues':report,'cpuSeconds':time.process_time()-cpu,'newMonteCarloRuns':0,'calibrated':False,'historicalMarketPricesUsed':False,'originalInjuryPublicationComplete':False})
