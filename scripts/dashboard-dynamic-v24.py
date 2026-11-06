"""Build a compact, read-only dashboard cache; no UI-triggered computation."""
import sys,json,gzip,importlib.util
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import atomic,read
OUT=ROOT/'artifacts/dynamic-v24'
def run():
    summary=read(OUT/'analysis/summary.json');cases=read(OUT/'continuation/results.json')['cases'];sample={}
    for case in cases:
        p=OUT/'continuation'/(case['gameId'].replace(':','_')+'.json.gz');r=json.loads(gzip.decompress(p.read_bytes()));actual=r['initialActual'];wanted=('passingAttempts','passingYards','carries','rushingYards','receptions','receivingYards') if case['sport']!='NBA' else ('points','rebounds','assists','threePointersMade','steals','blocks','pointsReboundsAssists');players=[]
        for pid,observed in actual['players'].items():
            if pid.startswith('team-stat') or not any(observed.get(k,0)>0 for k in wanted):continue
            for stat in wanted:
                d=r['playerDistributions'].get(pid,{}).get(stat)
                if d and observed.get(stat,0)>0:players.append({'player':pid,'stat':stat,'actual':observed.get(stat,0),'mechanicalFinalMean':d['mean'],'mechanicalRemainingMean':d['mean']-observed.get(stat,0),'interval90':d['interval90'],'thresholdProbability':None})
        sample[case['sport']]={'gameId':case['gameId'],'scores':actual['scores'],'period':actual['period'],'remaining':actual['remaining'],'games':8,'players':players[:8],'mode':'historical_mechanics','winProbability':None,'lastVerifiedTimestamp':r['researchContext']['sources'][-1].get('retrievedAt'),'source':r['researchContext']['sources'][-1]['source'],'label':'Historical checkpoint. Final-conditioned mechanics samples; not a live forecast.','modelVersion':'24.0-research','forecastStatus':'withheld'}
    leagues={}
    for s,windows in summary['sequential'].items():
        tasks=[]
        for task in ('actions','shots') if s=='NBA' else ('actions','drives'):
            rows=[w['tasks'][task] for w in windows if w['tasks'].get(task,{}).get('status')=='evaluated'];tasks.append({'task':task,'events':sum(r['events'] for r in rows),'games':sum(r['games'] for r in rows),'logLoss':{v:sum(r['metrics'][v]['logLoss']*r['events'] for r in rows)/sum(r['events'] for r in rows) for v in ('A','B','C')} if rows else {},'decision':summary['eventDecisions'][s][task]})
        heads=[{'stat':h['stat'],'family':h.get('bestFirstWindowFamily'),'estimand':h.get('pointEstimand'),'retained':h.get('pointResearchCandidate',False),'baselineMAE':h['windows'][-1]['baseline']['mae'],'candidateMAE':h['windows'][-1]['candidate']['mae'],'games':h['windows'][-1]['candidate']['games'],'coverage90':h['windows'][-1]['candidate']['interval90Coverage']} for h in summary['leaderboard'] if h['sport']==s and h['status']=='conditional_evaluated'];leagues[s]={'tasks':tasks,'pointGames':summary['pointValidationGames'][s],'heads':heads,'checkpoint':sample.get(s)}
    r={'version':24,'generatedAt':datetime.now(timezone.utc).isoformat(),'dataMode':'historical_research','liveEnabled':False,'leagues':leagues,'blockers':summary['blocks'],'strictPregameGames':0,'strictLiveReplayGames':0,'productionPromotions':0};atomic(ROOT/'docs/research/dynamic-v24-dashboard.json',r);print('Cached research dashboard built; no live probabilities published')
if __name__=='__main__':run()
