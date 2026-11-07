"""Bounded source-to-ledger experiments; final-conditioned, never forecasts.

Extends the existing V23 input/replay and V24 specialized adapters. No new
registry, tournament or deployment. Freeze selection before running a variant.
"""
import sys,json,gzip,hashlib,runpy,pickle,time,resource,csv
from pathlib import Path
from collections import defaultdict
import numpy as np
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import digest,read
from modeling.iterative_learning import freeze_json
from modeling.integration_v22.datasets import protected,cfb_packets
from modeling.overnight_v20.data import archives
from modeling.fullgame_v23.modes import Mode,context
from modeling.fullgame_v23.replay import football_replay,football_book_totals
from modeling.fullgame_v23.nba_replay import replay as nba_replay
from modeling.fullgame_v23.kernel_inputs import nfl_kernel_rows,cfb_kernel_rows
from modeling.fullgame_v23.timing import nba_action_intervals
from modeling.fullgame_v23.accounting import team_actor
from modeling.dynamic_v24.football import PlayKernel,mechanics_games
from modeling.dynamic_v24.completion.joint import HeadFootballKernel,football_mechanics,nba_rates,nba_mechanics
from modeling.fullgame_v23.clock_phases import PhaseClockLaw,nfl_stopped_live_pairs,explicit_cfb_live_pairs
from modeling.fullgame_v23.gamebook import primary_actions,reconcile
from modeling.accuracy_v25.joint_session import bounded_call
OUT=ROOT/'artifacts/evidence-and-joint-v27'
BASE=runpy.run_path(str(ROOT/'scripts/fullgame-v23.py'))


def canonical(sport,gid):
    return gid if sport=='NFL' or ':' in gid else ('nba:espn:' if sport=='NBA' else 'cfb:espn:')+gid


def load():
    owned,oldraw=BASE['inputs']();ban=protected();data=archives('NFL');ps=pq.read_table(ROOT/'artifacts/fullgame-v23/sources/stats_player_week_2024.parquet').to_pylist();ts=pq.read_table(ROOT/'artifacts/fullgame-v23/sources/stats_team_week_2024.parquet').to_pylist()
    mapping={'passingAttempts':'attempts','completions':'completions','passingYards':'passing_yards','carries':'carries','rushingYards':'rushing_yards','receptions':'receptions','receivingYards':'receiving_yards'}
    teamrows=defaultdict(dict);playerrows=defaultdict(list)
    for r in ts:teamrows[r['game_id']][r['team']]=r
    for r in ps:playerrows[r['game_id']].append(r)
    for gid,g in data['games'].items():
        if gid in ban or g['season']!=2024 or gid not in teamrows:continue
        game={'id':gid,'sport':'NFL','at':g['firstObservedAt'],'season':2024,'home':g['home'],'away':g['away'],'teams':{}}
        for t in (g['home'],g['away']):
            tr=teamrows[gid].get(t)
            if tr is None:break
            players={r['player_id']:{'stats':{k:float(r[v] or 0) for k,v in mapping.items()},'name':r['player_display_name']} for r in playerrows[gid] if r['team']==t and r['player_id'] and sum(float(r.get(k) or 0) for k in ('attempts','carries','targets','receptions'))>0}
            totals={k:float(tr[v]) for k,v in mapping.items()};totals.update(score=g['actualHome'] if t==g['home'] else g['actualAway'],offensivePlays=tr['attempts']+tr['carries']+tr['sacks_suffered'])
            game['teams'][t]={'players':players,'totals':totals}
        if len(game['teams'])==2:owned['NFL'][gid]=game
    cs,_=cfb_packets();owned['CFB'].update({g['id']:g for g in cs})
    selection_path=OUT/('selection-nfl-clock.json' if '--nfl-clock-only' in sys.argv else 'selection-nba-expansion.json' if '--nba-expansion' in sys.argv else 'selection-clock-eligible.json' if '--eligible-clock-cohort' in sys.argv else 'selection.json')
    selection=read(selection_path)
    if selection is None:
        chosen={}
        for sport in ('NFL','CFB','NBA'):
            base=list(BASE['SELECTION'][sport]);clock_eligible='--eligible-clock-cohort' in sys.argv and sport=='CFB'
            candidates=sorted((g for g in owned[sport].values() if g['season'] in (2024,2025) and g['id'] not in ban and g['id'] not in base and (not clock_eligible or g['at']>'2024-09-20T00:00:00Z')),key=lambda g:(g.get('at',''),g['id']))
            chosen[sport]=base+[g['id'] for g in candidates[:12-len(base)]]
        selection={'selection':chosen,'scope':'historical_mechanics_only','sourceSelection':'Existing gamebook cases plus earliest unprotected available 2024/25 boxes; selection before simulation outputs','seed':270027,'trialsPerCase':4,'protectedIdsSHA256':digest(sorted(ban))}
        if '--eligible-clock-cohort' in sys.argv:selection['revisionReason']='Additional CFB mechanics inputs must follow the fixed V21 clock training cutoff; no clock-fit temporal gate bypass, no selection on score or simulation result.'
        freeze_json(selection_path,selection)
    raw={};paths={'NFL':'/tmp/gridiron-nfl-pbp-2024.parquet','CFB':'/tmp/gridiron-cfb-public-pbp-2024.parquet','NBA':'/tmp/gridiron-nba-pbp-2025.parquet'}
    for sport,ids in selection['selection'].items():
        if not ids:raw[sport]={};continue
        if set(ids)&ban:raise ValueError('Protected selection')
        parsed=ids if sport=='NFL' else [int(g.split(':')[-1]) for g in ids]
        rows=pq.read_table(paths[sport],filters=[('game_id','in',parsed)]).to_pylist();raw[sport]=defaultdict(list)
        for r in rows:raw[sport][canonical(sport,str(r['game_id']) if sport=='NFL' else str(int(r['game_id'])))].append(r)
        for gid in BASE['SELECTION'][sport]:raw[sport][gid]=oldraw[sport][gid]
    return owned,raw,selection,paths


def book(sport,gid):
    info=(read(OUT/'books.json',{})|read(OUT/'books-extra.json',{})|read(OUT/'books-expansion.json',{})).get(gid)
    if info and info.get('textPath'):return (ROOT/info['textPath']).read_text(),info
    if gid in BASE['BOOKS']:
        name=BASE['BOOKS'][gid]
        for folder in ('fullgame-v23','overnight-v21'):
            for r in read(ROOT/'artifacts'/folder/'gamebooks/manifest.json',[]):
                p=Path(r['path']);p=p if p.is_absolute() else ROOT/p
                candidates=[p.with_suffix('.txt'),ROOT/'artifacts/fullgame-v23/gamebooks'/(name+'.txt')]
                if p.stem==name:
                    for candidate in candidates:
                        if candidate.exists():return candidate.read_text(),r
    return None,None


def corrected_cfb(gid,game,raw,text,source):
    labels={'cfb:espn:401635556':({'jamesmadison':game['away'],'northcarolina':game['home']},{'JMU':game['away'],'UNC':game['home']}),'cfb:espn:401643793':({'ballst':game['away'],'ballstate':game['away'],'jamesmadison':game['home']},{'BSU':game['away'],'JMU':game['home']}),'cfb:espn:401628497':({'minnesota':game['away'],'michigan':game['home']},{'MIN':game['away'],'UoM':game['home']}),'cfb:espn:401628439':({'georgiatech':game['away'],'georgia':game['home']},{'GT':game['away'],'UGA':game['home']})}
    if not text or gid not in labels:return raw,[]
    names,codes=labels[gid];acts=primary_actions(text,names,codes)
    if max(int(r.get('period') or 0) for r in raw)>4:
        # The primary adapter identifies regulation plays only. Its matching
        # assumptions must not be applied across repeated untimed OT clocks.
        return raw,explicit_cfb_live_pairs(acts,source)
    fixed,_=reconcile(raw,acts,source,{t:v['players'] for t,v in game['teams'].items()})
    return fixed,explicit_cfb_live_pairs(acts,source)


def summaries(result,sport):
    out=[]
    for r in result['results']:
        teams=r['team'];players=r['players']
        if sport=='NBA':
            exact=all(sum(p.get('points',0) for pid,p in players.items() if result['_owners'].get(pid)==t)==v['points'] for t,v in teams.items())
            out.append({'scores':r['scores'],'possessions':r['possessions'],'regulationAndOTSeconds':r['seconds'],'overtimePeriods':r['overtimePeriods'],'reboundable':r['reboundableMisses'],'rebounded':r['creditedRebounds'],'playerPointsEqualTeamPoints':exact,'actions':sum(r['possessions'].values()),'substitutions':r['substitutions']})
        else:
            out.append({'scores':r['scores'],'teamPlays':{t:v['offensivePlays'] for t,v in teams.items()},'actions':r['actions'],'regulationDrives':r['regulationDriveStarts'],'regulationSeconds':r['regulationSeconds'],'periodCharges':r['periodCharges'],'overtimePeriods':r['overtimePeriods'],'passingReceivingEqual':all(v['passingYards']==v['receivingYards'] for v in teams.values())})
    return out


def run(tag,phase=False):
    if not tag.replace('-','').isalnum():raise ValueError('Safe revision ID required')
    folder=OUT/tag;owned,raw,selection,paths=load()
    codepaths=[Path(__file__),*sorted((ROOT/'modeling/dynamic_v24').glob('*.py')),*sorted((ROOT/'modeling/dynamic_v24/completion').glob('*.py')),*sorted((ROOT/'modeling/fullgame_v23').glob('*.py'))]
    implementation={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in codepaths}
    trials=2 if '--eligible-clock-cohort' in sys.argv else 4
    protocol={'selection':selection,'implementation':implementation,'phaseClock':phase,'conditionalClock':'--conditional-clock' in sys.argv,'trialsPerCase':trials,'sourceVersions':{s:hashlib.sha256(Path(p).read_bytes()).hexdigest() for s,p in paths.items()},'accuracyClaim':False,'forecastTrials':0,'maximumCPUSeconds':180}
    freeze_json(folder/'protocol.json',protocol);cases=[]
    freeze_json(folder/'code-editions.json',{str(p.relative_to(ROOT)):p.read_text() for p in codepaths})
    for sport,ids in selection['selection'].items():
        for gid in ids:
            game=owned[sport][gid];rows=raw[sport][gid];text,source=book(sport,gid);sources=[{'source':'https://github.com/'+('nflverse/nflverse-data' if sport=='NFL' else 'sportsdataverse/sportsdataverse-data'),'sourceVersion':protocol['sourceVersions'][sport],'role':'final_conditioned_mechanics'}]
            if source:sources.append(source)
            ctx=context(Mode.MECHANICS,sport,gid,sources);replay_info={};pairs=[]
            try:
                if sport=='NBA':
                    if text is None:raise ValueError('Independent NBA gamebook unavailable')
                    rep=nba_replay(game,rows,text,ctx)
                    replay_info={k:rep[k] for k in ('completeAccountingReplay','scoreReconciled','allPlayerStatsReconciled','minuteBudgetReconciled','reconstructedPlayerMinutesAllExact','allEventLineupsIdentified')}
                    replay_info['countingDifferences']=sum(not r['equal'] for r in rep['statComparisons'])
                else:
                    if sport=='CFB':rows,pairs=corrected_cfb(gid,game,rows,text,source)
                    rep=football_replay(rows,game,game,ctx);replay_info={k:rep[k] for k in ('completeAccountingReplay','scoreReconciled','teamAccountingReconciled','playerAccountingReconciled','clock')}
                    replay_info['countingDifferences']=sum(not r['equal'] for r in rep['teamComparisons']+rep['playerComparisons']);replay_info['observedDrivePairs']=rep['driveIdentityPairs']
                    if text:replay_info['independentBookTotals']=football_book_totals(text,sport,[game['away'],game['home']])
            except (ValueError,AssertionError,KeyError) as e:replay_info={'completeAccountingReplay':False,'reason':str(e)}
            if '--replay-only' in sys.argv:
                case={'sport':sport,'gameId':gid,'variant':'source_replay_only','games':0,'replay':replay_info,'sourceVersion':protocol['sourceVersions'][sport],'historicalBookSource':source,'forecastAccuracyEvaluated':False}
                freeze_json(folder/'cases'/(sport+'-'+gid.replace(':','_')+'-replay.json'),case);cases.append(case)
                print(json.dumps({'sport':sport,'gameId':gid,'replay':replay_info.get('completeAccountingReplay'),'reason':replay_info.get('reason'),'differences':replay_info.get('countingDifferences')}),flush=True);continue
            for variant in ('reference','specialized'):
                case={'sport':sport,'gameId':gid,'variant':variant,'replay':replay_info,'sourceVersion':protocol['sourceVersions'][sport],'historicalBookSource':source,'forecastAccuracyEvaluated':False}
                try:
                    if sport=='NBA':
                        intervals,_=nba_action_intervals(rows);est={str(int(p['athlete_id'])):{'minutes':float(p['minutes']),'points':float(p['points']),'fieldGoalAttempts':float(p['field_goals_attempted']),'threePointAttempts':float(p['three_point_field_goals_attempted']),'freeThrowAttempts':float(p['free_throws_attempted']),'rebounds':float(p['offensive_rebounds']+p['defensive_rebounds']),'assists':float(p['assists'])} for p in game['players'] if float(p.get('minutes') or 0)>0}
                        manifest={'sport':sport,'estimand':'conditional_mean','modelVersions':['V24-source-mean-mechanical-probe'],'finalConditionedFallback':True}
                        adapted=game if variant=='reference' else nba_rates(game,est,manifest,ctx)
                        result=nba_mechanics(adapted,ctx,games=trials,seed=270027,clock_intervals=intervals);result['_owners']={str(int(p['athlete_id'])):str(p['team_id']) for p in game['players']}
                        # Source parquet dates are datetime values; canonical
                        # JSON ISO strings bind their values without dropping
                        # fields or coercing player/stat identities.
                        frozen_rates=json.loads(json.dumps(adapted,default=lambda v:v.isoformat()))
                        case['modelConfiguration']={'engine':result['engineVersion'],'ratesHash':digest(frozen_rates),'clockHash':digest(intervals),'headManifest':adapted.get('specializedHeadManifest')};case['headDiagnostics']=adapted.get('headDiagnostics')
                    else:
                        teams=[game['home'],game['away']];owners={p:t for t,v in game['teams'].items() for p in v['players']};prepared,diagnostics=(nfl_kernel_rows if sport=='NFL' else cfb_kernel_rows)(rows,game);est={p:{k:float(x) for k,x in v['stats'].items() if k in ('passingAttempts','passingYards','carries','rushingYards','receptions','receivingYards')} for t,vv in game['teams'].items() for p,v in vv['players'].items()};est={p:v for p,v in est.items() if v}
                        for t,v in game['teams'].items():
                            credits={k:float(x) for k,x in v.get('unassignedTeamCredits',{}).items() if k in ('passingAttempts','passingYards','carries','rushingYards','receptions','receivingYards')}
                            if credits:owners[team_actor(t)]=t;est[team_actor(t)]=credits
                        kwargs={}
                        if '--conditional-clock' in sys.argv:kwargs['condition_clock']=True
                        if sport=='CFB':
                            from modeling.integration_v22.clock import RuntimeClock,serialize_clock
                            kwargs['clock_model']=RuntimeClock(serialize_clock(pickle.load((ROOT/'artifacts/overnight-v21/clock/censored_drive_em2.pickle').open('rb'))),game['at'])
                            kwargs['additional_clock_pools']={'kneel':[r['elapsed'] for r in archives('CFB')['rows'] if r['kind']=='kneel' and r.get('elapsed') is not None and 1<=r['elapsed']<=90 and r['at']<game['at'] and r['game'] not in protected()]}
                        if phase:
                            if sport=='NFL':pairs=nfl_stopped_live_pairs(rows,sources[0])
                            kwargs['phase_clock']=PhaseClockLaw(pairs,sport)
                        kernel=PlayKernel(sport,teams,prepared,owners,**kwargs) if variant=='reference' else HeadFootballKernel(sport,teams,prepared,owners,estimates=est,head_manifest={'sport':sport,'estimand':'conditional_mean','modelVersions':['V24-source-mean-mechanical-probe'],'finalConditionedFallback':True},**kwargs)
                        extra=[];two=[]
                        for event in (r for rs in raw[sport].values() for r in rs):
                            if sport=='NFL':
                                if event.get('extra_point_attempt'):extra.append(int(event.get('extra_point_result')=='good'))
                                if event.get('two_point_attempt'):two.append(int(event.get('two_point_conv_result')=='success'))
                            else:
                                if event.get('xp_attempt'):extra.append(int(bool(event.get('xp_made'))))
                                if event.get('two_point_conv_result') is not None:two.append(int(event['two_point_conv_result']=='success'))
                        result=mechanics_games(kernel,ctx,game['season'],trials,270027,{'extra_point':extra,'two_point':two}) if variant=='reference' else football_mechanics(kernel,ctx,game['season'],games=trials,seed=270027,conversions={'extra_point':extra,'two_point':two})
                        case['modelConfiguration']={'engine':result['engineVersion'],'kernelInputHash':kernel.input_hash,'headsHash':digest(est) if variant=='specialized' else None};case['inputAdapterDiagnostics']=diagnostics;case['headDiagnostics']=getattr(kernel,'headDiagnostics',None);case['phaseClockDiagnostics']=result.get('phaseClockDiagnostics')
                    config=case['modelConfiguration'];model={'sport':sport,'implementationHash':digest(implementation),'configuration':config,'inputPolicy':'final_conditioned_mechanics_only','productionEligible':False};case['modelHash']=digest(model);case['model']=model
                    case.update(status='completed',games=trials,mechanicalInvariantsPassed=result['mechanicalInvariantsPassed'],simulated=summaries(result,sport))
                except (ValueError,AssertionError,KeyError) as e:case.update(status='withheld',games=0,reason=str(e))
                freeze_json(folder/'cases'/(sport+'-'+gid.replace(':','_')+'-'+variant+'.json'),case);cases.append(case)
                print(json.dumps({'sport':sport,'gameId':gid,'variant':variant,'status':case['status'],'games':case['games'],'reason':case.get('reason'),'sourceReplayComplete':replay_info.get('completeAccountingReplay')}),flush=True)
    report={'version':27,'mode':'historical_mechanics','implementationHash':digest(implementation),'protocolHash':digest(protocol),'cases':cases,'newStrictForecasts':0,'independentAccuracyGames':0,'productionWrites':0,'modelsPromoted':0,'gamesByLeague':{s:sum(c['games'] for c in cases if c['sport']==s) for s in selection['selection']}}
    freeze_json(folder/'results.json',report)
    print(json.dumps({'summary':report['gamesByLeague'],'newStrictForecasts':0}),flush=True)


if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    if '--prepare' in sys.argv:
        _,_,selection,_=load();print(json.dumps(selection,indent=2))
    else:
        tag=sys.argv[sys.argv.index('--id')+1];start=time.monotonic();cpu=time.process_time()
        status='failed'
        try:
            with bounded_call(180,360):run(tag,'--phase-clock' in sys.argv)
            status='completed'
        finally:
            receipt={'status':status,'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-start,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
            freeze_json(OUT/tag/'receipt.json',receipt);print(json.dumps(receipt))
