"""Read-only grading of FROZEN forecasts against separate verified outcomes.
Never imports actuals into fitting. Old forecasts and PBP-based grades survive.
Common pregame support avoids diluting player MAE with all receivers' zero passes.
No historical lines, original publication times or calibrated probabilities invented.
"""
import sys,json,gzip,time,hashlib,math
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import freeze_json,distribution_errors
from modeling.calibration_research import metrics,paired_interval
from modeling.structural_v18.models import error_metrics,cluster_delta,FAMILIES
from modeling.structural_v18.data import packets
from modeling.reconstruction_v19.outcomes import player_outcome
from modeling.reconstruction_v19.registry import Registry,BoundedLoop
from modeling.reconstruction_v19.runtime import local_only
OUT=ROOT/'artifacts/parallel-v19'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def checksum(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stat_summary(rows):
    if not rows:return None
    out=error_metrics([r['actual'] for r in rows],[r['mean'] for r in rows]);out.update(games=len({r['gameId'] for r in rows}),players=len({r.get('id',r.get('player')) for r in rows}))
    if all('coverage' in r for r in rows):out['interval90Coverage']=float(np.mean([r['coverage']['0.9']['covered'] for r in rows]));out['crps']=float(np.mean([r['crps'] for r in rows]))
    return out

def teams(f):
    if f['sport']=='NBA':return {'nba:espn:'+p:t for t,v in f['rotationAssumptions'].items() for p in v['minutes']}
    return {p:t for t,v in f['participantAssumptions'].items() for p in set(v['receivers'])|set(v['runners'])|{v['quarterback']}}

def official_grade(archive,box,support,common):
    f=archive['forecast'];mapping=teams(f);rs=[];missing=[]
    for pid,ss in f['players'].items():
      if pid not in common:continue
      for stat,d in ss.items():
        if (pid,stat) not in support:continue
        y,why=player_outcome(box,pid,mapping[pid],stat)
        if y is None:missing.append({'player':pid,'stat':stat,'reason':why});continue
        rs.append({'gameId':archive['game']['id'],'id':pid,'team':mapping[pid],'stat':stat,**distribution_errors(d,y)})
    h,a=f['home'],f['away'];scores=box['scores'];actual_margin=scores[h]-scores[a]
    return {'gameId':archive['game']['id'],'sport':f['sport'],'candidate':archive['candidate'],'cohort':archive['game']['cohort'],'probability':f['homeWinProbability'],'truth':int(scores[h]>scores[a]),'ties':scores[h]==scores[a],'score':[distribution_errors(f['scoreDistributions'][t],scores[t]) for t in (h,a)],'margin':distribution_errors(f['marginDistribution'],actual_margin),'total':distribution_errors(f['totalDistribution'],scores[h]+scores[a]),'players':rs,'missing':missing,'forecastPlayers':len(f['players']),'unmodeledActualParticipants':sum(p not in f['players'] for p in box['players']),'scoringSource':'independent_official_box','outcomesVerified':True,'forecastSha256':checksum(archive['_path']),'scheduledStart':box['scheduledStart'],'informationCutoff':archive['snapshot']['informationCutoff'],'cutoffBeforeScheduledStart':archive['snapshot']['informationCutoff']<box['scheduledStart'],'notForPregameFeatures':True}

def mc_summary(grades):
    categories=defaultdict(list)
    for g in grades:
        for row in g['players']:categories[row['stat']].append(row|{'gameId':g['gameId']})
    binary=[g for g in grades if not g['ties']];fav=[max(g['probability'],1-g['probability']) for g in binary];hit=[int((g['probability']>=.5)==bool(g['truth'])) for g in binary]
    return {'games':len(grades),'windows':len({g['cohort'] for g in grades}),'moneyline':metrics([g['probability'] for g in binary],[g['truth'] for g in binary]),'favoriteReliability':metrics(fav,hit),'coinFlipBaseline':metrics([.5]*len(binary),[g['truth'] for g in binary]),'teamScore':error_metrics([r['actual'] for g in grades for r in g['score']],[r['mean'] for g in grades for r in g['score']]),'margin':stat_summary([g['margin']|{'gameId':g['gameId'],'id':'team'} for g in grades]),'total':stat_summary([g['total']|{'gameId':g['gameId'],'id':'team'} for g in grades]),'byStat':{s:stat_summary(v) for s,v in categories.items()},'byWindow':{str(c):{'moneyline':metrics([g['probability'] for g in binary if g['cohort']==c],[g['truth'] for g in binary if g['cohort']==c]),'teamScoreMAE':float(np.mean([abs(r['error']) for g in grades if g['cohort']==c for r in g['score']]))} for c in sorted({g['cohort'] for g in grades})},'unmodeledActualParticipants':sum(g['unmodeledActualParticipants'] for g in grades),'rawOnly':True,'calibratedProbability':None}

def compare(ref,challenger):
    pairs=[(ref[g],challenger[g]) for g in sorted(set(ref)&set(challenger))];common_stats=set(r['stat'] for a,b in pairs for r in a['players']);by_stat={}
    for stat in sorted(common_stats):
        base=[];cand=[];rs=[]
        for a,b in pairs:
            aa={(r['id'],r['stat']):r for r in a['players'] if r['stat']==stat};bb={(r['id'],r['stat']):r for r in b['players'] if r['stat']==stat}
            for key in sorted(set(aa)&set(bb)):rs.append({'gameId':a['gameId'],'y':aa[key]['actual']});base.append(aa[key]['mean']);cand.append(bb[key]['mean'])
        if rs:
            before=error_metrics([r['y'] for r in rs],base);after=error_metrics([r['y'] for r in rs],cand);by_stat[stat]={'before':before,'after':after,'paired':cluster_delta(rs,base,cand),'relativeMAEChange':(after['mae']/before['mae']-1) if before['mae'] else None}
    return {'teamScore':paired_interval([np.mean([abs(r['error']) for r in a['score']]) for a,b in pairs],[np.mean([abs(r['error']) for r in b['score']]) for a,b in pairs]),'brier':paired_interval([(a['probability']-a['truth'])**2 for a,b in pairs if not a['ties']],[(b['probability']-b['truth'])**2 for a,b in pairs if not a['ties']]),'logLoss':paired_interval([-math.log(max(1e-12,a['probability'] if a['truth'] else 1-a['probability'])) for a,b in pairs if not a['ties']],[-math.log(max(1e-12,b['probability'] if b['truth'] else 1-b['probability'])) for a,b in pairs if not a['ties']]),'byStat':by_stat,'resampling':'paired game-cluster bootstrap, 1000 draws; descriptive small-sample intervals, no multiple-testing claim'}

def main():
    local_only()
    if (ROOT/'docs/reports/parallel-v19-results-v2.json').exists():
        print(json.dumps({'status':'frozen_report_available','results':'docs/reports/parallel-v19-results-v2.json','newSimulations':0}));return
    cpu=time.process_time();protocol=read(OUT/'protocol.json');nba={p['id']:p for p in packets('NBA')};report={};official={}
    for path in (OUT/'outcomes').glob('*.official.json.gz'):
        b=read(path)['box'];official[b['eventId']]=b
    for sport in ['NFL','CFB','NBA']:
        allfiles=list((OUT/'runs'/sport).glob('*/*.forecast.json.gz'));events=defaultdict(list);by=defaultdict(dict)
        for file in allfiles:
            a=read(file);a['_path']=file;events[a['game']['id']].append(a)
        for gid,aa in events.items():
            common=set.intersection(*(set(a['forecast']['players']) for a in aa));support={(p,s) for a in aa for p,ss in a['forecast']['players'].items() for s,d in ss.items() if any(h['value']!=0 and h['count']>0 for h in d['histogram'])}
            for a in aa:
                fp=a['_path']
                if sport!='NBA':g=official_grade(a,official[gid],support,common)
                else:
                    g=read(fp.with_name(fp.name.replace('.forecast','.evaluation')));g.update(cohort=a['game']['cohort'],outcomesVerified=True,scoringSource='reconciled_complete_official_box_archive');g['players']=[r|{'gameId':gid} for r in g['players'] if r['id'] in common and (r['id'],r['stat']) in support]
                    f=a['forecast'];h,away=f['home'],f['away'];scores={t:v['totals']['score'] for t,v in nba[gid]['teams'].items()};g.update(margin=distribution_errors(f['marginDistribution'],scores[h]-scores[away]),total=distribution_errors(f['totalDistribution'],scores[h]+scores[away]))
                if sport!='NBA':
                    own=official_grade(a,official[gid],{(p,s) for p,ss in a['forecast']['players'].items() for s,d in ss.items() if any(h['value']!=0 and h['count']>0 for h in d['histogram'])},set(a['forecast']['players']))
                    g['ownPregameSupportPlayers']=own['players']
                    g['notInCommonPregameSupport']=sorted(set(a['forecast']['players'])-common)
                else:g['ownPregameSupportPlayers']=g['players']
                freeze_json(fp.with_name(fp.name.replace('.forecast','.official-evaluation-v2')),g);by[a['candidate']][gid]=g
        summaries={c:mc_summary(list(gs.values())) for c,gs in by.items()};paired={c:compare(by['frozen_reference'],gs) for c,gs in by.items() if c!='frozen_reference'};report[sport]={'fullGameComparisons':summaries,'pairedVsFrozenReference':paired,'allForecastsPreserved':True,'projectionComparisons':{},'selectedGames':len(protocol['selection'][sport]),'fullGameGames':len(events),'pregameAvailabilityCoverage':0.,'strictPointInTimeReplayQualifiedGames':0,'finalTestEvaluated':False}
        # Corrected point-projection comparison, all five unchanged model families.
        projection=read(OUT/'projections'/(sport+'.json.gz'));lookup={(r['gameId'],r['player'],r['stat']):r for r in projection['rows']};scored=defaultdict(list);rejected=defaultdict(int)
        for r in projection['rows']:
            if sport!='NBA' and r['stat'] in ('passingTouchdowns','receivingTouchdowns','rushingTouchdowns'):rejected['invalid_zero_label_head']+=1;continue
            if r['player'].split(':')[-1].startswith('-'):rejected['team_stat_actor_not_individual']+=1;continue
            if sport!='NBA':
                box=official[r['gameId']]
                if r['player']=='__team__':y=box['scores'].get(r['team']) if r['stat']=='score' else box['teamStatTotals'].get(r['team'],{}).get(r['stat'])
                else:y,_=player_outcome(box,r['player'],r['team'],r['stat'])
            else:
                box=nba[r['gameId']]['teams'][r['team']];y=box['totals'].get(r['stat']) if r['player']=='__team__' else box['players'].get(r['player'],{}).get('stats',{}).get(r['stat'],0)
            if y is None:rejected['unsupported_official_statistic']+=1;continue
            group=('team:' if r['player']=='__team__' else '')+r['stat'];scored[group].append(r|{'actual':y})
        for group,rs in scored.items():
            result={}
            for family in FAMILIES:
                result[family]={**error_metrics([r['actual'] for r in rs],[r['predictions'][family] for r in rs]),'games':len({r['gameId'] for r in rs}),'players':len({r['player'] for r in rs}),'pairedVsRolling':cluster_delta([r|{'y':r['actual']} for r in rs],[r['predictions']['rolling5'] for r in rs],[r['predictions'][family] for r in rs])}
            report[sport]['projectionComparisons'][group]=result
        for candidate,gs in by.items():
            own_rows=[r|{'gameId':g['gameId']} for g in gs.values() for r in g['ownPregameSupportPlayers']]
            report[sport]['fullGameComparisons'][candidate]['ownPregameSupportByStat']={st:stat_summary([r for r in own_rows if r['stat']==st]) for st in sorted({r['stat'] for r in own_rows})}
            matched=defaultdict(list)
            for g in gs.values():
                for row in g['players']:
                    pid=row['id'].split(':')[-1] if sport=='NBA' else row['id'];pr=lookup.get((g['gameId'],pid,row['stat']))
                    if pr and not (sport!='NBA' and row['stat'] in ('passingTouchdowns','rushingTouchdowns','receivingTouchdowns')):matched[row['stat']].append(row|{'rolling':pr['predictions']['rolling5'],'gameId':g['gameId']})
            report[sport]['fullGameComparisons'][candidate]['matchedRolling5Comparisons']={st:{'observations':len(rs),'games':len({r['gameId'] for r in rs}),'rolling':error_metrics([r['actual'] for r in rs],[r['rolling'] for r in rs]),'simulation':error_metrics([r['actual'] for r in rs],[r['mean'] for r in rs]),'paired':cluster_delta([r|{'y':r['actual']} for r in rs],[r['rolling'] for r in rs],[r['mean'] for r in rs])} for st,rs in matched.items()}
        report[sport].update(projectionGames=len({r['gameId'] for rs in scored.values() for r in rs}),projectionExcluded=dict(rejected))
        freeze_json(OUT/'projection-official-grades'/(sport+'.json.gz'),dict(scored))
    frozen={'leagues':report,'rawSimulationProbabilitiesOnly':True,'promoted':[],'newCalibrators':0,'newFinalTestGames':0,'availabilityCoverageDenominator':'Complete verified pregame availability per game, not isolated player facts.','gradingPolicy':'Independent official box scores for both football leagues; new grades supersede old PBP-derived grades without replacing any forecast. Common pregame player support across candidates; nonzero pregame category support excludes irrelevant all-zero roles.','researchTiming':'Retrospective corrected statistical archives; original publication coverage incomplete. Selected validation IDs are disjoint from v15/v16/v18 development, but not a genuinely untouched final test.','cpuSeconds':time.process_time()-cpu}
    freeze_json(ROOT/'docs/reports/parallel-v19-results-v2.json',frozen);print(json.dumps({'leagues':{s:{'projectionGames':v['projectionGames'],'fullGameGames':v['fullGameGames'],'candidates':{c:{'scoreMAE':m['teamScore']['mae'],'brier':m['moneyline']['brier'],'logLoss':m['moneyline']['logLoss'],'ece':m['moneyline']['ece']} for c,m in v['fullGameComparisons'].items()}} for s,v in report.items()},'cpuSeconds':time.process_time()-cpu}),flush=True)
if __name__=='__main__':main()
