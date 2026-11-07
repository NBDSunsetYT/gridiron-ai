"""Grade saved V26 references after final results; never regenerate forecasts.

Uses the existing source parser and scoring concepts. No model fitting,
simulation, wager settlement, DB write or production promotion occurs.
"""
import sys,json,gzip,hashlib,runpy,re
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import digest,read
from modeling.iterative_learning import freeze_json
from modeling.accuracy_v20.quality import aware
from modeling.accuracy_v25.opportunity_calendar import observed


def due(game,when):
    if aware(game['forecastCapturedAt'])>=aware(game['eventAt']):raise ValueError('Saved forecast was not captured before kickoff')
    return when>=aware(game['eventAt'])+timedelta(hours=4)


def verify_snapshot(snapshot):
    if snapshot.get('sha256')!=digest({k:v for k,v in snapshot.items() if k!='sha256'}):raise ValueError('Forecast snapshot checksum mismatch')
    for g in snapshot['games']:
        if g.get('predictionHash')!=digest({k:v for k,v in g.items() if k!='predictionHash'}):raise ValueError('Saved game forecast checksum mismatch')
        due(g,aware(g['eventAt'])) # timestamp check only; no source requests


def main(snapshot_paths=None,output_root=None,public_prefix='V26'):
    tag=sys.argv[sys.argv.index('--id')+1] if '--id' in sys.argv else datetime.now(timezone.utc).strftime('grade-%Y%m%dT%H%M%S')
    if not re.fullmatch('[A-Za-z0-9_-]{1,60}',tag):raise ValueError('Safe unique grade ID required')
    if not re.fullmatch(r'V[0-9]+',public_prefix):raise ValueError('Versioned public grading prefix required')
    out=(Path(output_root) if output_root is not None else ROOT/'artifacts/accuracy-v26/grades')/tag;out.mkdir(parents=True,exist_ok=True)
    protocol=read(out/'protocol.json')
    if protocol is None:
        protocol={'createdAt':datetime.now(timezone.utc).isoformat(),'operation':'grade_saved_prospective_references_only','noRefit':True,'noProductionWrites':True}
        freeze_json(out/'protocol.json',protocol)
    when=aware(protocol['createdAt']);versions={}
    paths=snapshot_paths or {r:ROOT/'docs/research'/('V26_PROSPECTIVE_'+r+'.json.gz') for r in ('R1','R2')}
    for revision,p in paths.items():
        snapshot=json.loads(gzip.decompress(Path(p).read_bytes()));verify_snapshot(snapshot);versions[revision]=snapshot
    capture=runpy.run_path(str(ROOT/'scripts/v26-capture.py'));capture['get'].__globals__['OUT']=out/'source-probes'
    parser=runpy.run_path(str(ROOT/'scripts/v26-forecast.py'));actuals={};pending=[]
    for game in next(iter(versions.values()))['games']:
        key=(game['sport'],game['eventId'])
        if not due(game,when):pending.append({'sport':key[0],'eventId':key[1],'reason':'Future/not-yet-due game; no final-stat request made'});continue
        url='https://site.api.espn.com/apis/site/v2/sports/'+capture['LEAGUES'][key[0]]+'/summary?event='+key[1]
        raw,receipt=capture['get'](url)
        if raw is None:pending.append({'sport':key[0],'eventId':key[1],'reason':'Final source unavailable'});continue
        data=json.loads(raw);header=data.get('header',{});comp=header.get('competitions',[{}])[0]
        if str(header.get('id'))!=key[1] or comp.get('status',{}).get('type',{}).get('completed') is not True:
            pending.append({'sport':key[0],'eventId':key[1],'reason':'Event identity mismatch or source not final'});continue
        final=parser['normalized'](data,key[0])
        if set(final['teams'])!={t['teamId'] for t in game['teams']}:raise ValueError('Actual teams differ from saved forecast')
        actuals[key]=(data,final,receipt)
    evaluations=[];ungraded=[];withheld=[]
    for revision,snapshot in versions.items():
        for game in snapshot['games']:
            key=(game['sport'],game['eventId'])
            if key not in actuals:continue
            raw,final,receipt=actuals[key]
            for team,value in game['modeBConditionalReferences']['score'].items():
                if value is not None:evaluations.append({'revision':revision,'sport':key[0],'gameId':key[1],'player':'__team__:'+team,'stat':'teamPoints','predictedMean':value,'predictedMedian':None,'actual':final['teams'][team]['score'],'sourceVersion':receipt['sourceVersion'],'scope':'conditional_score_reference_not_joint_simulation'})
            for player in game['players']:
                if not player.get('reference'):
                    withheld.append({'revision':revision,'sport':key[0],'gameId':key[1],'player':player['playerId'],'reason':player.get('withheld','Withheld before outcome')});continue
                for stat,prediction in player['reference'].items():
                    y,proof=observed(final,raw,key[0],player['teamId'],player['playerId'],stat)
                    if y is None:ungraded.append({'revision':revision,'sport':key[0],'gameId':key[1],'player':player['playerId'],'stat':stat,'reason':proof});continue
                    evaluations.append({'revision':revision,'sport':key[0],'gameId':key[1],'player':player['playerId'],'stat':stat,'name':player['name'],'predictedMean':prediction['mean'],'predictedMedian':prediction['median'],'actual':y,'availabilityAtForecast':player['availability'],'actualProof':proof,'sourceVersion':receipt['sourceVersion'],'scope':'conditional_player_reference_not_validated_forecast'})
    grouped=defaultdict(list)
    for row in evaluations:grouped[(row['revision'],row['sport'],row['stat'])].append(row)
    metrics=[]
    for (revision,sport,stat),rows in sorted(grouped.items()):
        e=np.array([r['predictedMean']-r['actual'] for r in rows]);metrics.append({'revision':revision,'sport':sport,'stat':stat,'games':len({r['gameId'] for r in rows}),'observations':len(rows),'mae':float(np.mean(abs(e))),'rmse':float(np.sqrt(np.mean(e*e))),'bias':float(np.mean(e)),'brier':None,'logLoss':None,'crps':None,'intervalCoverage':None,'calibration':None,'reason':'Only frozen point references; no invented probability/distribution or validated interval'})
    report={'version':'prospective-grading-26.0','createdAt':protocol['createdAt'],'metrics':metrics,'evaluations':evaluations,
            'pendingGames':pending,'ungradedMissingActuals':ungraded,'withheldBeforeOutcome':withheld,
            'sourceVersions':[{'sport':key[0],'eventId':key[1],'source':r[2]['url'],'sourceVersion':r[2]['sourceVersion'],'capturedAt':r[2]['retrievedAt']} for key,r in actuals.items()],
            'actualSourceClass':'Public ESPN final boxes, secondary provider; official NBA CDN access was unavailable during capture',
            'allForecastsPreserved':True,'modelFits':0,'MonteCarloGames':0,'productionPromotion':False,
            'comparisonPolicy':'Report each frozen revision separately; changed coverage is not claimed as paired accuracy improvement',
            'statisticallyEstablishedImprovement':False,'strictJointValidationClaim':False}
    freeze_json(out/'results.json',report)
    if actuals:freeze_json(ROOT/'docs/research'/(public_prefix+'_GRADES_'+tag+'.json.gz'),report)
    print(json.dumps({'finalGamesRetrieved':len(actuals),'gradedObservations':len(evaluations),'pending':pending,'modelsPromoted':0}),flush=True)


if __name__=='__main__':main()
