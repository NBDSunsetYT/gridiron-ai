"""Accuracy-first read-only audit of frozen validation and source evidence.
No simulations, external API calls, tuning or production writes are performed.
"""
import sys,json,gzip,math,time,hashlib
from pathlib import Path
from collections import defaultdict,Counter
from datetime import timedelta,datetime,timezone
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20 import data
from modeling.overnight_v20.sources import protocol
from modeling.overnight_v20.cohort import training_rows
from modeling.overnight_v20.state import atomic,digest,read
from modeling.accuracy_v20.quality import assess,aware
from modeling.accuracy_v20.attribution import opportunity_efficiency,nba_rebound_attribution
from modeling.accuracy_v20.benchmarks import OpponentAdjustedRolling
from modeling.accuracy_v20.snapshots import ResearchSnapshots
from modeling.accuracy_v20.decisions import review
from modeling.iterative_learning import freeze_json,unrealism_flags
from modeling.structural_v18.models import error_metrics
from modeling.calibration_research import paired_interval,metrics
OUT=ROOT/'artifacts/overnight-v20';AUDIT=OUT/'accuracy-first';AUDIT.mkdir(exist_ok=True)
def unpack(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def key(r):return (r['gameId'],r['team'],r.get('player',r.get('id')),r['stat'])
def template(g,source,version,classification='inferred',**extra):return {'eventId':g['id'],'source':source,'sourceVersion':version,'publishedAt':None,'retrievedAt':None,'classification':classification,'complete':False,**extra}
def evidence_components(g,pid,team,evidence,history_rows):
    source='https://github.com/nflverse/nflverse-data' if g['sport']=='NFL' else 'https://github.com/sportsdataverse';version=digest(protocol()['sourceFiles']);c={k:template(g,source,version) for k in ['identity','historical_statistics','lineup','participation','weather']};c['identity']['reason']='Current stable IDs verified; original schedule publication is unverified';c['historical_statistics']['reason']='Earlier completed-game evidence with six-hour embargo; original correction/publication timestamp unknown';c['participation']['reason']='Previous opportunities/minutes observed; original snap/rotation publication and next-game participation unknown';c['lineup']['classification']='unavailable';c['lineup']['reason']='No confirmed original pregame starting lineup in this research archive';c['weather']['classification']='unavailable';c['weather']['reason']='No original pregame weather forecast in this research archive'
    if history_rows:c['historical_statistics']['latestObservedGameEnd']=max(r['end'] for r in history_rows)
    cutoff=aware(g['at'])-timedelta(minutes=30);facts=[r for r in evidence['facts'] if r['eventId']==g['id'] and (not pid or r['playerId']==pid) and (not team or r['teamId']==team) and r['publishedAt'] and aware(r['publishedAt'])<=cutoff]
    if facts:
        f=max(facts,key=lambda r:r['publishedAt']);c['injury']=template(g,f['source'],f['sourceVersion'],'confirmed',publishedAt=f['publishedAt'],retrievedAt=f['retrievedAt'],complete=pid is not None,playerId=pid,observedStatuses=sorted({r['status'] for r in facts}),reason='Verified player designation; team-wide absence of reports still does not mean healthy')
    else:c['injury']=template(g,source,version,'unavailable',reason='No exact player-specific pregame injury/availability fact' if pid else 'No complete team injury/availability evidence')
    return c
def compare_rows(rows,family):
    rs=[r for r in rows if family in r['predictions'] and 'rolling5' in r['predictions']];by=defaultdict(list)
    for r in rs:by[r['gameId']].append((abs(r['predictions']['rolling5']-r['actual']),abs(r['predictions'][family]-r['actual'])))
    before=[np.mean([a for a,b in v]) for v in by.values()];after=[np.mean([b for a,b in v]) for v in by.values()]
    return {'games':len(by),'observations':len(rs),'metrics':error_metrics([r['actual'] for r in rs],[r['predictions'][family] for r in rs]) if rs else None,'baseline':error_metrics([r['actual'] for r in rs],[r['predictions']['rolling5'] for r in rs]) if rs else None,'pairedMAEDelta':paired_interval(before,after,20020) if rs else None}
def benchmark_cohort(folder,sport,packets,evidence):
    forecast=unpack(folder/'point-forecasts.json.gz');games=[g for g in protocol()['selection'][sport] if g['cohort']==int(folder.name.split('-')[-1])];cutoff=forecast['fitCutoff'];rows,_=training_rows(packets,cutoff);grouped=defaultdict(list)
    for r in rows:
        if r['player']!='__team__':grouped[r['stat']].append(r)
    fits={};unsupported={}
    for stat,items in grouped.items():
        try:fits[stat]=OpponentAdjustedRolling().fit(items)
        except ValueError as e:unsupported[stat]=str(e)
    history=defaultdict(list)
    for g in packets:
        for t in [g['home'],g['away']]:history[t].append(g)
    mapped={};records=[]
    for g in games:
        for team in [g['home'],g['away']]:
            by=defaultdict(list)
            for r in data.features_for(g,team,history,sport):
                if r['player']!='__team__' and not r['player'].split(':')[-1].startswith('-'):by[r['stat']].append(r)
            for stat,items in by.items():
                if stat not in fits:continue
                for r,value in zip(items,fits[stat].predict(items)):
                    outs=[f for f in evidence['facts'] if f['eventId']==g['id'] and f['playerId']==r['player'] and f['status'].lower() in ('out','inactive','injured_reserve') and aware(f['publishedAt'])<=aware(g['at'])-timedelta(minutes=30)];value=0. if outs else float(value);mapped[key(r)]=value;records.append({'key':list(key(r)),'prediction':value,'featureSha256':digest(r['x'])})
    # This frozen benchmark precedes this command's access to grading files.
    body={'sport':sport,'cohort':folder.name,'fitCutoff':cutoff,'forecasts':records,'unsupported':unsupported,'historicalReplay':True,'originalPublicationsComplete':False,'productionPromotion':False};freeze_json(AUDIT/'benchmarks'/(folder.name+'-'+digest(body)+'.json.gz'),body)
    grades=unpack(folder/'point-grades.json.gz') if (folder/'point-grades.json.gz').exists() else []
    for r in grades:
        if key(r) in mapped:r['predictions']['opponent_adjusted_rolling']=mapped[key(r)]
    return grades
def audit():
    begin=time.process_time();report={'version':'accuracy-first-v20.1','recordedAt':datetime.now(timezone.utc).isoformat(),'productionWrites':0,'productionPromotions':0,'reservedFinalOpened':False,'retrospectiveCorrectedHistory':True,'scoreMeaning':'Evidence score measures timestamped source coverage, not accuracy.','uncertaintyMeaning':'Numerical Monte Carlo intervals do not quantify injury/lineup/model uncertainty.','leagues':{},'systematicErrors':[],'marketBenchmark':{'verifiedHistoricalThresholds':0,'status':'Unavailable in this campaign; no invented betting grades, external probabilities or ensemble weights.'},'stopReason':'Further tuning paused pending evidence-quality and distributional audit.'};quality_rows=[];attributions=[];snap=ResearchSnapshots(AUDIT/'snapshots.sqlite')
    for sport in ['NFL','CFB','NBA']:
        packets=data.packets(sport);original=data.archives(sport)
        if sport=='NBA':original={g['id']:g for g in original.values()}
        evidence=unpack(OUT/'evidence'/(sport+'-aligned-v3.json.gz'));history=defaultdict(list)
        for g in packets:
            for t in [g['home'],g['away']]:history[t].append(g)
        gamequality={};playerquality={}
        for g in protocol()['selection'][sport]:
            cut=(aware(g['at'])-timedelta(minutes=30)).isoformat();hq=[h for t in [g['home'],g['away']] for h in history[t] if aware(h['end'])+timedelta(hours=6)<aware(cut)];q=assess(sport,g['id'],cut,evidence_components(g,None,None,evidence,hq));quality_rows.append(q);gamequality[g['id']]=q
            for team in [g['home'],g['away']]:
                players={r['player'] for r in data.features_for(g,team,history,sport) if r['player']!='__team__' and not r['player'].split(':')[-1].startswith('-')}
                for pid in players:
                    q=assess(sport,g['id'],cut,evidence_components(g,pid,team,evidence,hq),pid);quality_rows.append(q);playerquality[(g['id'],pid)]=q
        points=[];simgrades=defaultdict(list);frozen=[];folders=sorted((OUT/'experiments/r1/cohorts').glob(sport+'-*'))
        for folder in folders:
            if (folder/'point-forecasts.json.gz').exists():points.extend(benchmark_cohort(folder,sport,packets,evidence))
            for variant in (folder/'grades').glob('*'):
                simgrades[variant.name].extend(unpack(p) for p in variant.glob('*.json.gz'))
            frozen.extend(folder.glob('forecasts/*/*.json.gz'))
        # Preserve already completed hurdle results; incomplete work stays pending.
        hurdles={}
        for p in (OUT/'hurdle').glob(sport+'-*/grades.json.gz'):
            for r in unpack(p):hurdles[key(r)]=r['predictions']['hurdle']
        existing={key(r) for r in points}
        for p in (OUT/'hurdle').glob(sport+'-*/grades.json.gz'):
            for r in unpack(p):
                if key(r) not in existing:points.append({**r,'predictions':{'rolling5':r['predictions']['rolling5'],'opportunity_hurdle':r['predictions']['hurdle']}});existing.add(key(r))
        for r in points:
            if key(r) in hurdles:r['predictions']['opportunity_hurdle']=hurdles[key(r)]
        index={key(r):r for r in points};conflicts=[]
        for p in (OUT/'point-only/cohorts').glob(sport+'-*/grades.json.gz'):
            for r in unpack(p):
                previous=index.get(key(r))
                if previous is None:points.append(r);index[key(r)]=r;continue
                if r['actual']!=previous['actual']:raise ValueError('Official grade changed: preserve correction as another evaluation version')
                for family,value in r['predictions'].items():
                    if family in previous['predictions'] and abs(value-previous['predictions'][family])>1e-8:
                        conflicts.append({'eventId':r['gameId'],'player':r['player'],'stat':r['stat'],'model':family,'old':previous['predictions'][family],'new':value});previous['predictions']['accuracy_suite:'+family]=value
                    else:previous['predictions'][family]=value
        if sport=='NBA':
            completion=read(OUT/'point-only/outcome-completion-receipt.json',{'completed':[]})
            for item in completion['completed']:
                for r in unpack(ROOT/item['artifact'])['rows']:
                    if key(r) in index:raise ValueError('A supposedly missing NBA grade already exists; preserve as a separate correction version')
                    points.append(r);index[key(r)]=r
        pg=[r for r in points if r['player']!='__team__'];cats={s:[r for r in pg if r['stat']==s] for s in sorted({r['stat'] for r in pg})};bench={s:{f:compare_rows(rs,f) for f in sorted({f for r in rs for f in r['predictions']})} for s,rs in cats.items()};matched={}
        for variant,grades in simgrades.items():
            lookup={(r['gameId'],r['team'],('nba:espn:'+r['player'] if sport=='NBA' else r['player']),r['stat']):r for r in pg};paired=[]
            for g in grades:
                for r in g['players']:
                    identity=(g['gameId'],r['team'],r['id'],r['stat']);row=lookup.get(identity)
                    if row:paired.append({**row,'predictions':{**row['predictions'],'simulator:'+variant:r['mean']}})
            matched[variant]={stat:{f:compare_rows([r for r in paired if r['stat']==stat],f) for f in sorted({f for r in paired if r['stat']==stat for f in r['predictions']})} for stat in sorted({r['stat'] for r in paired})}
        distributions={}
        for variant,grades in simgrades.items():
            rows=[r for g in grades for r in g['players']];prob=[g for g in grades if not g['ties']];distributions[variant]={'games':len(grades),'rawMoneyline':metrics([g['probability'] for g in prob],[g['truth'] for g in prob]) if prob else None,'calibratedMoneyline':None,'categories':{s:{'observations':len(rs),'meanCRPS':float(np.mean([r['crps'] for r in rs])),'coverage':{str(level):float(np.mean([r['coverage'][str(level)]['covered'] for r in rs])) for level in [.5,.8,.9,.95]}} for s in sorted({r['stat'] for r in rows}) if (rs:=[r for r in rows if r['stat']==s])}}
        warnings=[];replay=0
        for fp in frozen:
            archive=unpack(fp);f=archive['forecast'];g=archive['game'];q=gamequality[g['id']];flags=unrealism_flags(f);warnings.extend({'eventId':g['id'],'variant':archive['variant'],'flag':flag} for flag in flags)
            snap.freeze({'eventId':g['id'],'eventStart':g['at'],'predictionAsOf':q['predictionCutoff'],'modelVersion':f['modelVersion'],'inputHash':f['inputDataVersion'],'seed':f['seed'],'simulations':f['simulations'],'phase':'historical_replay','forecastReference':str(fp.relative_to(ROOT)),'forecastSha256':hashlib.sha256(fp.read_bytes()).hexdigest(),'playerIds':list(f['players']),'evidencePolicy':q['policyVersion'],'selectiveDecision':q['decision'],'originalCreatedAt':f['createdAt']})
            # Only already graded current events may enter diagnostic attribution.
            gradepath=fp.parent.parent.parent/'grades'/archive['variant']/fp.name
            if not gradepath.exists():continue
            grade=unpack(gradepath);ps={(r['id'],r['stat']):r for r in grade['players']};roles=f.get('rotationAssumptions') if sport=='NBA' else f.get('participantAssumptions');teamids={}
            for team,r in roles.items():
                ids=set(r['minutes']) if sport=='NBA' else {r['quarterback'],*r['receivers'],*r['runners'],*f.get('quarterbackScenarioPlans',{}).get(team,{}).get('ids',[])}
                for pid in ids:teamids['nba:espn:'+pid if sport=='NBA' else pid]=team
            if sport=='NBA':
                raw=original[g['id']];actualplayers={('nba:espn:'+str(p['athlete_id'])):p for p in raw['players']};sums={t:{s:sum(z.get(s,{}).get('mean',0) for pid,z in f['players'].items() if teamids.get(pid)==t) for s in ['offensiveRebounds','defensiveRebounds','minutes']} for t in [g['home'],g['away']]}
            for (pid,stat),r in ps.items():
                if stat not in (['rebounds'] if sport=='NBA' else ['passingYards','receivingYards','rushingYards','receptions']):continue
                z=f['players'].get(pid)
                if not z:continue
                if sport!='NBA':
                    op='passingAttempts' if stat=='passingYards' else 'carries' if stat=='rushingYards' else 'targets';actual=ps.get((pid,op));opdist=z.get(op)
                    if not actual or not opdist:a={'available':False,'reason':'Verified matching opportunity distribution/outcome unavailable'}
                    else:a=opportunity_efficiency(opdist['mean'],actual['actual'],r['mean'],r['actual'])
                else:
                    team=r['team'];other=g['away'] if team==g['home'] else g['home'];t=raw['teams'][team];opp=raw['teams'][other];actual=actualplayers.get(pid);actualmins=float(actual['minutes']) if actual else 0.;teammins=sum(float(p['minutes'] or 0) for p in raw['players'] if str(p['team_id'])==team)
                    total_pred=sums[team]['offensiveRebounds']+sums[other]['defensiveRebounds']+sums[team]['defensiveRebounds']+sums[other]['offensiveRebounds'];total_actual=t['offensive_rebounds']+opp['defensive_rebounds']+t['defensive_rebounds']+opp['offensive_rebounds'];a=nba_rebound_attribution(z['minutes']['mean'],actualmins,sums[team]['minutes']/5,teammins/5,total_pred,total_actual,r['mean'],r['actual'])
                attributions.append({'sport':sport,'gameId':g['id'],'variant':archive['variant'],'playerId':pid,'stat':stat,'attribution':a})
        primary='rebounds' if sport=='NBA' else 'passingYards';rows=cats.get(primary,[])
        for family in sorted({f for r in rows for f in r['predictions']}):
            c=compare_rows(rows,family);report['systematicErrors'].append({'sport':sport,'stat':primary,'model':family,**c,'relativeMAE':c['metrics']['mae']/c['baseline']['mae'] if c['metrics'] and c['baseline']['mae'] else None})
        coverage={'games':len(gamequality),'players':len(playerquality),'completePointInTimeGames':sum(not q['missingDomains'] for q in gamequality.values()),'unconditionalForecastsWithheld':sum(q['decision']=='withhold_unconditional_forecast' for q in gamequality.values()),'playersWithVerifiedAvailabilityFact':sum('injury' in q['verifiedDomains'] for q in playerquality.values()),'gameMissingDomains':dict(Counter(d for q in gamequality.values() for d in q['missingDomains'])),'meanGameEvidenceScore':float(np.mean([q['pointInTimeEvidenceScore'] for q in gamequality.values()])),'meanPlayerEvidenceScore':float(np.mean([q['pointInTimeEvidenceScore'] for q in playerquality.values()])) if playerquality else None}
        attrib=[r for r in attributions if r['sport']==sport];byattrib={}
        for stat in sorted({r['stat'] for r in attrib}):
            selected=[r for r in attrib if r['stat']==stat and r['variant']=='v19_reference' and r['attribution'].get('available')];valid=[r['attribution'] for r in selected];keys={k for r in valid for k in r['signedContributions']};byattrib[stat]={'modelFrame':'Frozen V19 comparison implementation; supported opportunity distributions only','games':len({r['gameId'] for r in selected}),'observations':len(valid),'meanSignedContributions':{k:float(np.mean([r['signedContributions'].get(k,0) for r in valid])) for k in keys},'meanAbsoluteErrorContributions':{k:float(np.mean([r['absoluteErrorContributions'].get(k,0) for r in valid])) for k in keys},'maxReconciliationResidual':max((abs(r['reconciliationResidual']) for r in valid),default=None),'unidentified':sorted({u for r in valid for u in r['unidentifiedComponents']})}
        phasebench={phase:{s:{f:compare_rows(rs,f) for f in sorted({f for r in rs for f in r['predictions']})} for s in sorted({r['stat'] for r in selected}) if (rs:=[r for r in selected if r['stat']==s])} for phase,selected in [('development',[r for r in pg if r['cohort']==0]),('validation',[r for r in pg if r['cohort']!=0])]}
        seasonbench={str(season):{s:{f:compare_rows(rs,f) for f in sorted({f for r in rs for f in r['predictions']})} for s in sorted({r['stat'] for r in selected}) if (rs:=[r for r in selected if r['stat']==s])} for season in sorted({r['season'] for r in pg}) if (selected:=[r for r in pg if r['season']==season])}
        windows=[{'cohort':c,'phase':'development' if c==0 else 'validation','start':min(g['at'] for g in protocol()['selection'][sport] if g['cohort']==c),'end':max(g['at'] for g in protocol()['selection'][sport] if g['cohort']==c),'fit':unpack(folder/'point-forecasts.json.gz')['fitCutoff']} for folder in folders if (folder/'point-forecasts.json.gz').exists() if (c:=int(folder.name.split('-')[-1]))>=0]
        for folder in (OUT/'point-only/cohorts').glob(sport+'-*'):
            if not (folder/'forecasts.json.gz').exists():continue
            c=int(folder.name.split('-')[-1])
            if any(w['cohort']==c for w in windows):continue
            metadata=unpack(folder/'forecasts.json.gz');events=[g for g in protocol()['selection'][sport] if g['cohort']==c];windows.append({'cohort':c,'phase':'development' if c==0 else 'validation','start':min(g['at'] for g in events),'end':max(g['at'] for g in events),'fit':metadata['fitCutoff']})
        report['leagues'][sport]={'evidenceCoverage':coverage,'evaluatedProjectionGames':len({r['gameId'] for r in pg}),'playerObservations':len(pg),'benchmarkSuite':bench,'phaseBenchmarks':phasebench,'seasonBenchmarks':seasonbench,'walkForward':sorted(windows,key=lambda w:w['start']),'matchedFullGameBenchmarks':matched,'probabilityAndIntervals':distributions,'attribution':byattrib,'forecastGuardWarnings':warnings,'sameHeadReplayConflicts':conflicts,'promotionQualified':False,'validationWindowsCompleted':sorted({r['cohort'] for r in points}),'historicalFinalTestOpened':False,'missingMarketBenchmark':True}
        report['leagues'][sport]['candidateDecisions']={f:review(report['leagues'][sport],sport,f) for f in sorted({f for r in pg for f in r['predictions']}) if f!='rolling5'}
    body={'rows':quality_rows,'policy':'Equal-weight original publication coverage, not a model confidence score'};qh=freeze_json(AUDIT/('quality-'+digest(body)+'.json.gz'),body);ah=freeze_json(AUDIT/('attribution-'+digest(attributions)+'.json.gz'),attributions);snap.backup(AUDIT/'snapshots-backup.sqlite');snap.close();report.update(qualityArtifactSha256=qh,attributionArtifactSha256=ah,cpuSeconds=time.process_time()-begin,attributionCaveat='Descriptive algebra, not causal error diagnosis. Football snap time, true NBA on-court misses and separate pace/efficiency causes are unidentifiable in these archives. Distribution adequacy is scored separately.');report['systematicErrors'].sort(key=lambda r:r['relativeMAE'] if r['relativeMAE'] is not None else -1,reverse=True)
    report['quarantined']=[{'eventId':d['game']['id'],'sport':d['game']['sport'],'flags':d['unrealismFlags'],'scoreMeans':{t:v['mean'] for t,v in d['forecast']['scoreDistributions'].items()},'environment':d['forecast']['gameEnvironment'],'productionPublished':False} for p in (OUT/'diagnostics').glob('*.json.gz') if (d:=unpack(p)).get('quarantined')]
    report['sealedFinalSelectionsHash']=digest(protocol()['sealedFinal']);report['clockSourceAudit']=read(AUDIT/'clock-diagnostic.json');report['outcomeCompletionAudit']=read(OUT/'point-only/outcome-completion-receipt.json');report['stopReason']='Accuracy-first suite completed; further full-game tuning withheld pending reliable clock, original pregame lineup/availability and model-uncertainty evidence.';atomic(AUDIT/'report.json',report);atomic(ROOT/'docs/reports/accuracy-first-v20.json',report);print(json.dumps({'leagues':{s:{'coverage':v['evidenceCoverage'],'evaluatedGames':v['evaluatedProjectionGames']} for s,v in report['leagues'].items()},'cpuSeconds':report['cpuSeconds'],'hostedCompute':0},indent=2));return report
if __name__=='__main__':audit()
