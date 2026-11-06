"""Resumable, registered Mode A replay and complete-game mechanics campaign."""
import sys,json,pickle,importlib.util,hashlib,gzip
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.fullgame_v23.io import OUT
from modeling.fullgame_v23.runtime import job,verify_parent
from modeling.fullgame_v23.clock_phases import PhaseClockLaw,explicit_cfb_live_pairs,nfl_stopped_live_pairs
from modeling.fullgame_v23.gamebook import primary_actions,reconcile
from modeling.fullgame_v23.kernel_inputs import cfb_kernel_rows,nfl_kernel_rows
from modeling.fullgame_v23.football import PlayKernel,mechanics_games as football_games
from modeling.fullgame_v23.basketball import mechanics_games as nba_games
from modeling.fullgame_v23.forecast import compact
from modeling.fullgame_v23.replay import football_replay,football_book_totals
from modeling.fullgame_v23.nba_replay import replay as nba_replay
from modeling.fullgame_v23.timing import nba_action_intervals
from modeling.fullgame_v23.rules import FootballOvertime
from modeling.integration_v22.clock import RuntimeClock,serialize_clock
from modeling.overnight_v20.state import atomic,read
from modeling.iterative_learning import freeze_json
spec=importlib.util.spec_from_file_location('replay23',ROOT/'scripts/fullgame-v23.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
NAME='verified-r5'
LABELS={'cfb:espn:401635556':({'jamesmadison':'cfb:espn:256','northcarolina':'cfb:espn:153'},{'JMU':'cfb:espn:256','UNC':'cfb:espn:153'}),'cfb:espn:401643793':({'ballst':'cfb:espn:2050','ballstate':'cfb:espn:2050','jamesmadison':'cfb:espn:256'},{'BSU':'cfb:espn:2050','JMU':'cfb:espn:256'}),'cfb:espn:401628497':({'minnesota':'cfb:espn:135','michigan':'cfb:espn:130'},{'MIN':'cfb:espn:135','UoM':'cfb:espn:130'}),'cfb:espn:401628439':({'georgiatech':'cfb:espn:59','georgia':'cfb:espn:61'},{'GT':'cfb:espn:59','UGA':'cfb:espn:61'})}

def run():
    packets,raw=s.inputs();folder=OUT/NAME;folder.mkdir(exist_ok=True);contexts={};resolved={};observations={'NFL':[],'CFB':[]};actions={};proofs={};summary=[]
    for sport,ids in s.SELECTION.items():
        for gid in ids:
            ctx=s.source_context(sport,gid);contexts[gid]=ctx;rows=raw[sport][gid];book=OUT/'gamebooks'/(s.BOOKS.get(gid,'unavailable')+'.txt');game=packets[sport][gid]
            if sport=='NFL':observations['NFL']+=nfl_stopped_live_pairs(rows,ctx['sources'][0])
            if sport=='CFB':
                names,codes=LABELS[gid];acts=primary_actions(book.read_text(),names,codes);actions[gid]=acts;observations['CFB']+=explicit_cfb_live_pairs(acts,ctx['sources'][-1])
                if max(int(r['period']) for r in rows)<=4:rows,proofs[gid]=reconcile(rows,acts,ctx['sources'][-1],{t:v['players'] for t,v in game['teams'].items()})
            resolved[gid]=rows;path=folder/'replay'/(gid.replace(':','_')+'.json.gz')
            if path.exists():r=s.unpack(path)
            else:
                r=nba_replay(game,rows,book.read_text(),ctx) if sport=='NBA' else football_replay(rows,game,game,ctx)
                if sport!='NBA' and book.exists():
                    ref=football_book_totals(book.read_text(),sport,[game['away'],game['home']]);r['independentBookComparisons']=[{'team':t,'stat':stat,'official':v,'replayed':r['team'][t].get(stat,0),'equal':v==r['team'][t].get(stat,0)} for stat,values in ref.items() for t,v in values.items()];r['independentBookAllEqual']=bool(ref) and all(v['equal'] for v in r['independentBookComparisons'])
                freeze_json(path,r)
            if gid in proofs and not (folder/'reconciliation'/(gid.replace(':','_')+'.json.gz')).exists():freeze_json(folder/'reconciliation'/(gid.replace(':','_')+'.json.gz'),proofs[gid])
            if not r['completeAccountingReplay']:raise ValueError('Independent accounting replay failed '+gid)
            summary.append({'sport':sport,'gameId':gid,'completeAccountingReplay':True,'scoreReconciled':r['scoreReconciled'],'referenceScores':r['referenceScores'],'independentBook':book.exists(),'clock':r.get('clock'),'minuteBudgetReconciled':r.get('minuteBudgetReconciled'),'allLineupsIdentified':r.get('allEventLineupsIdentified'),'playerCountingComparisons':len(r.get('playerComparisons',r.get('statComparisons',[]))),'countingDifferences':sum(not v['equal'] for v in r.get('playerComparisons',r.get('statComparisons',[]))),'anonymousCredits':r.get('unassignedIdentityCounts')});print('Replayed',sport,gid,flush=True)
    if not (folder/'live-clock-observations.json.gz').exists():freeze_json(folder/'live-clock-observations.json.gz',observations)
    frozen=pickle.load((ROOT/'artifacts/overnight-v21/clock/censored_drive_em2.pickle').open('rb'));archive={sport:s.data.archives(sport)['rows'] for sport in ['NFL','CFB']};banned=s.protected();generated=[]
    for sport,ids in s.SELECTION.items():
        for gi,gid in enumerate(ids):
            path=folder/'games'/(gid.replace(':','_')+'.json.gz');ctx=contexts[gid];game=packets[sport][gid];seed=23001+gi
            if path.exists():result=s.unpack(path);generated.append(result['mechanicsSummary']);continue
            if sport=='NBA':
                intervals,law=nba_action_intervals(raw[sport][gid]);r=nba_games(game,ctx,16,seed,intervals);repeated=nba_games(game,ctx,1,seed,intervals);diagnostics={'sourceClock':law}
            else:
                rows,adapter=(nfl_kernel_rows if sport=='NFL' else cfb_kernel_rows)(resolved[gid],game);owners={p:t for t,v in game['teams'].items() for p in v['players']};at=game['at'];timing=RuntimeClock(serialize_clock(frozen),at) if sport=='CFB' else None;clock_pools={}
                if sport=='CFB':clock_pools['kneel']=[int(r['elapsed']) for r in archive[sport] if r['kind']=='kneel' and r['game'] not in banned and r['at']<at and r.get('elapsed') is not None and 1<=r['elapsed']<=90]
                kernel=PlayKernel(sport,[game['home'],game['away']],rows,owners,timing,clock_pools,PhaseClockLaw(observations[sport],sport));extra=[];two=[]
                for rs in raw[sport].values():
                    for e in rs:
                        if sport=='NFL':
                            if e.get('extra_point_attempt'):extra.append(int(e.get('extra_point_result')=='good'))
                            if e.get('two_point_attempt'):two.append(int(e.get('two_point_conv_result')=='success'))
                        else:
                            if e.get('xp_attempt'):extra.append(int(bool(e.get('xp_made'))))
                            if e.get('two_point_conv_result') is not None:two.append(int(e['two_point_conv_result']=='success'))
                conversions={'extra_point':extra,'two_point':two};r=football_games(kernel,ctx,game['season'],16,seed,conversions);repeated=football_games(kernel,ctx,game['season'],1,seed,conversions);diagnostics={'adapter':adapter,'conversionCounts':{k:len(v) for k,v in conversions.items()}}
            deterministic=r['results'][0]==repeated['results'][0]
            if not deterministic:raise AssertionError('Seed replay differs '+gid)
            times=[row.get('regulationSeconds',row.get('seconds')) for row in r['results']];plays=[sum(t.get('offensivePlays',0) for t in row['team'].values()) for row in r['results']] if sport!='NBA' else None
            rec={'sport':sport,'gameId':gid,'completeConditionalMechanicsGames':16,'seed':seed,'deterministicFirstGameReplayed':deterministic,'allInvariantsPassed':True,'overtimeGames':sum(row['overtimePeriods']>0 for row in r['results']),'regulationSeconds':3600 if sport!='NBA' else 2880,'totalClockSecondsRange':[min(times),max(times)],'offensivePlayCountRange':[min(plays),max(plays)] if plays else None,'notAPregamePrediction':True}
            compacted=compact(r);compacted['mechanicsSummary']=rec;compacted['inputDiagnostics']=diagnostics;freeze_json(path,compacted);generated.append(rec);print('Generated',sport,gid,'16 complete mechanics games',flush=True)
    result={'historicalReplay':summary,'generatedMechanics':generated,'counts':{sport:{'accountingReplays':sum(r['sport']==sport for r in summary),'completeModeAGames':sum(r['completeConditionalMechanicsGames'] for r in generated if r['sport']==sport),'strictPregameMatchups':0} for sport in s.SELECTION},'randomSeedReplayGames':len(generated),'strictForecastTrials':0,'productionReferenceComparisons':None,'brierScore':None,'logLoss':None,'calibration':None,'predictiveAccuracyEstablished':False,'reason':'Mechanics Mode A is final-conditioned. Independent publication-complete pregame and model-bound full-game certificates remain missing.'};atomic(folder/'results.json',result);verify_parent();return result['counts']|{'seedReplayGames':len(generated),'strictForecastTrials':0}
if __name__=='__main__':
    if '--register' in sys.argv:
        files=[Path(__file__),ROOT/'scripts/fullgame-v23.py',*sorted((ROOT/'modeling/fullgame_v23').glob('*.py'))];inputs=[*sorted((OUT/'sources').glob('*raw.json.gz')),*sorted((OUT/'gamebooks').glob('*.txt'))]
        freeze_json(OUT/'specs'/(NAME+'.json'),{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'inputHashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'selection':s.SELECTION,'mode':'historical_mechanics','trialsPerMatchup':16,'seed':23001,'oneAdditionalSeedReplayPerMatchup':True,'noPredictiveAccuracyClaims':True,'forecastsAndProductionWrites':0})
    else:print(json.dumps(job(NAME,run,cpu=600,wall=1200),indent=2))
