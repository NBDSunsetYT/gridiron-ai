"""Earlier-game NFL pace experiment, conditional mechanics, not a forecast.

V27's clock candidate stays disabled. Train pools only on previous games;
freeze model inputs before grading target pace. Unsupported timing states
withhold a case. Penalty/timeout gaps are reported, not hidden in an accuracy
claim. No final-score target is used for fitting or model selection.
"""
import sys,json,re,hashlib,time,resource
from pathlib import Path
from collections import defaultdict
import numpy as np
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.integration_v22.datasets import protected
from modeling.dynamic_v24.stat_data import excluded_validation
from modeling.fullgame_v23.kernel_inputs import nfl_kernel_rows
from modeling.fullgame_v23.clock_phases import PhaseClockLaw,nfl_stopped_live_pairs
from modeling.fullgame_v23.modes import Mode,context
from modeling.dynamic_v24.football import PlayKernel,mechanics_games
from modeling.overnight_v20.state import digest
from modeling.iterative_learning import freeze_json
from modeling.accuracy_v25.joint_session import bounded_call
OUT=ROOT/'artifacts/forecast-certification-v28/nfl-pace-r2'

def run():
    start=time.monotonic();cpu=time.process_time();paths=[ROOT/'artifacts/overnight-v21/external/nfl-2026.parquet',Path('/tmp/gridiron-nfl-pbp-2025.parquet')];versions={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};source={'source':'https://github.com/nflverse/nflverse-data','sourceVersion':digest(versions)};banned=protected()|set(excluded_validation());by=defaultdict(list)
    columns='game_id game_date home_team away_team posteam qtr play_id play_type quarter_seconds_remaining game_seconds_remaining yardline_100 ydstogo down score_differential pass_attempt rush_attempt sack qb_kneel complete_pass passing_yards rushing_yards yards_gained interception fumble_lost passer_player_id rusher_player_id receiver_player_id field_goal_attempt field_goal_result punt_attempt kick_distance return_yards out_of_bounds fixed_drive penalty timeout extra_point_attempt extra_point_result two_point_attempt two_point_conv_result incomplete_pass touchdown'.split()
    for path in paths:
        schema=set(pq.read_schema(path).names)
        filters=[('game_id','not in',[g for g in protected() if g.startswith(('2025_','2026_'))])]
        if '2025' in path.name:filters.append(('week','>=',14))
        for r in pq.read_table(path,columns=[c for c in columns if c in schema],filters=filters).to_pylist():
            r['no_play']=r.get('play_type')=='no_play';by[r['game_id']].append(r)
    info={gid:{'id':gid,'at':rs[0]['game_date']+'T00:00:00Z','home':rs[0]['home_team'],'away':rs[0]['away_team']} for gid,rs in by.items()};chosen=[]
    for g in sorted(info.values(),key=lambda g:(g['at'],g['id'])):
        if g['id'] in banned or not g['id'].startswith('2026_'):continue
        earlier={t:[h for h in info.values() if h['at']<g['at'] and t in (h['home'],h['away'])] for t in (g['home'],g['away'])}
        if all(len(v)>=3 for v in earlier.values()):chosen.append(g)
        if len(chosen)==8:break
    protocol={'selected':[g['id'] for g in chosen],'scope':'chronological conditional mechanics component, NOT strict pregame forecast','selectionBeforePaceGrading':True,'variants':['phase_reference','phase_plus_V27_conditional_clock'],'training':'Previous three games per team, strictly before target date midnight UTC','trialsPerVariant':4,'maximumTrials':64,'seed':280028,'source':source,'exclusionHash':digest(sorted(banned)),'defaultClockCandidateEnabled':False,'sourceFiles':versions,'priorSeasonHistoryIncluded':True,'revisionReason':'R1 found no new 2026 cases with three within-season priors; add strictly earlier 2025 history, never target outcomes','codeSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};freeze_json(OUT/'protocol.json',protocol);cases=[]
    for game in chosen:
        teams=[game['home'],game['away']];rs=[];inputids={};players=defaultdict(dict)
        for t in teams:
            own=sorted((h for h in info.values() if h['at']<game['at'] and t in (h['home'],h['away'])),key=lambda h:(h['at'],h['id']))[-3:];inputids[t]=[h['id'] for h in own]
            for h in own:
                for r in by[h['id']]:
                    if r.get('posteam')!=t:continue
                    for key in ('passer_player_id','rusher_player_id','receiver_player_id'):
                        if r.get(key):players[t][r[key]]={}
        shell={'id':game['id'],'at':game['at'],'teams':{t:{'players':dict(players[t])} for t in teams}}
        for t in teams:
            for gid in inputids[t]:
                h=info[gid];earliershell=shell|{'id':gid,'at':h['at']};prepared,_=nfl_kernel_rows([r for r in by[gid] if r.get('posteam')==t],earliershell);rs.extend(prepared)
        assert all(r['at']<game['at'] for r in rs)
        owners={p:t for t in teams for p in players[t]};training=[r for gid in set(sum(inputids.values(),[])) for r in by[gid]];pairs=[]
        for gid in set(sum(inputids.values(),[])):pairs.extend(nfl_stopped_live_pairs(by[gid],source))
        extra=[int(r.get('extra_point_result')=='good') for r in training if r.get('extra_point_attempt')];two=[int(r.get('two_point_conv_result')=='success') for r in training if r.get('two_point_attempt')]
        frozen={'game':game,'earlierGameIds':inputids,'inputSHA256':digest(rs),'conversionSHA256':digest({'extra_point':extra,'two_point':two}),'clockPairsSHA256':digest(pairs),'targetOutcomesUsed':False};freeze_json(OUT/'inputs'/(game['id']+'.json'),frozen)
        row={'gameId':game['id'],'variants':{}}
        for flag,name in [(False,'phase_reference'),(True,'phase_plus_V27_conditional_clock')]:
            try:
                clock=PhaseClockLaw(pairs,'NFL');k=PlayKernel('NFL',teams,rs,owners,phase_clock=clock,condition_clock=flag);ctx=context(Mode.MECHANICS,'NFL',game['id'],[source]);result=mechanics_games(k,ctx,2026,games=4,seed=280028,conversions={'extra_point':extra,'two_point':two});sims=result['results']
                row['variants'][name]={'completedGames':len(sims),'kernelSHA256':k.input_hash,'mechanicalInvariants':result['mechanicalInvariantsPassed'],'regulationSecondsExact':all(s['regulationSeconds']==3600 for s in sims),'meanTotalOffensivePlays':float(np.mean([sum(t['offensivePlays'] for t in s['team'].values()) for s in sims])),'meanDriveStarts':float(np.mean([s['regulationDriveStarts'] for s in sims])),'overtimeGames':sum(s['overtimePeriods']>0 for s in sims),'clockDiagnostics':clock.diagnostics(),'backoffs':k.clock_backoffs}
            except (ValueError,AssertionError,KeyError) as e:row['variants'][name]={'completedGames':0,'withheld':str(e)}
        # Target labels enter only after both fixed model variants ran.
        target=[r for r in by[game['id']] if r.get('qtr',0)<=4];actions=[r for r in target if r.get('posteam') in teams and not r.get('no_play') and (r.get('pass_attempt') or r.get('rush_attempt') or r.get('sack'))];drives={(r['posteam'],r.get('fixed_drive')) for r in target if r.get('posteam') in teams and r.get('fixed_drive') is not None and r.get('play_type') in ('run','pass','punt','field_goal')}
        row['actualPBP']={'regulationOffensivePlays':len(actions),'driveIdentities':len(drives),'penaltyRows':sum(bool(r.get('penalty')) for r in target),'timeoutRows':sum(bool(r.get('timeout')) for r in target),'zeroAdjacentClockAnchors':sum(a.get('qtr')==b.get('qtr') and a.get('quarter_seconds_remaining')==b.get('quarter_seconds_remaining') for a,b in zip(target,target[1:])),'overtime':any(r.get('qtr',0)>4 for r in by[game['id']]),'independentGamebookReconciliation':False}
        cases.append(row);freeze_json(OUT/'cases'/(game['id']+'.json'),row);print(json.dumps(row),flush=True)
    paired=[c for c in cases if all(v.get('completedGames')==4 for v in c['variants'].values())];metrics={}
    for name in protocol['variants']:
        use=[c for c in cases if c['variants'][name].get('completedGames')==4];d=np.array([c['variants'][name]['meanTotalOffensivePlays']-c['actualPBP']['regulationOffensivePlays'] for c in use]);metrics[name]={'games':len(use),'offensivePlayMAE':float(np.mean(abs(d))) if len(d) else None,'bias':float(np.mean(d)) if len(d) else None,'meanModelPlays':float(np.mean([c['variants'][name]['meanTotalOffensivePlays'] for c in use])) if use else None,'meanActualRegulationPlays':float(np.mean([c['actualPBP']['regulationOffensivePlays'] for c in use])) if use else None}
    delta=np.array([abs(c['variants'][protocol['variants'][1]]['meanTotalOffensivePlays']-c['actualPBP']['regulationOffensivePlays'])-abs(c['variants'][protocol['variants'][0]]['meanTotalOffensivePlays']-c['actualPBP']['regulationOffensivePlays']) for c in paired]);ci=np.quantile(np.random.default_rng(280028).choice(delta,(4000,len(delta)),replace=True).mean(axis=1),[.025,.975]).tolist() if len(delta) else None
    report={'protocol':protocol,'cases':cases,'metrics':metrics,'pairedGames':len(paired),'candidateMinusReferenceGameMAE':float(np.mean(delta)) if len(delta) else None,'pairedInterval95':ci,'completedMechanicsGames':sum(v['completedGames'] for c in cases for v in c['variants'].values()),'strictForecasts':0,'candidateEnabled':False,'certifiedPaceDistribution':False,'decision':'Keep V27 candidate disabled: small conditional component sample; source-edition, independent gamebooks, timeout/penalty/return timing and full distribution certification remain required','cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-start,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss};freeze_json(OUT/'results.json',report);print(json.dumps({k:report[k] for k in ('metrics','pairedGames','pairedInterval95','completedMechanicsGames','cpuSeconds')}),flush=True)

if __name__=='__main__':
    with bounded_call(180,360):run()
