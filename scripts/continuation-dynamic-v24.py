"""Real-prefix Mode A continuation checks; never a live accuracy claim."""
import sys,json,gzip,pickle,hashlib,importlib.util
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.football import PlayKernel,remaining_games as football_remaining
from modeling.dynamic_v24.basketball import remaining_games as nba_remaining
from modeling.fullgame_v23.accounting import FootballLedger,BasketballLedger
from modeling.fullgame_v23.replay import football_replay
from modeling.fullgame_v23.forecast import compact
from modeling.fullgame_v23.kernel_inputs import nfl_kernel_rows,cfb_kernel_rows
from modeling.fullgame_v23.timing import nba_action_intervals
from modeling.fullgame_v23.ordering import canonical_order
from modeling.fullgame_v23.nba_replay import replay as nba_replay
from modeling.fullgame_v23.modes import Mode,context
from modeling.overnight_v20.state import atomic,read
from modeling.iterative_learning import freeze_json
spec=importlib.util.spec_from_file_location('v23',ROOT/'scripts/fullgame-v23.py');v23=importlib.util.module_from_spec(spec);spec.loader.exec_module(v23)
def run():
    packets,raw=v23.inputs();cases=[];details={}
    for sport,gid in [('NFL','2024_05_BAL_CIN'),('CFB','cfb:espn:401628439')]:
        game=packets[sport][gid];rows=raw[sport][gid];key='play_id' if sport=='NFL' else 'sequenceNumber';q='qtr' if sport=='NFL' else 'period';ctx=v23.source_context(sport,gid);ordered=sorted(rows,key=lambda r:r.get(key,0));anchor=next(r for r in ordered if r.get(q)==3 and r.get('down')==1 and (r.get('yardline_100') if sport=='NFL' else r.get('start.yardsToEndzone')) is not None);prefix=[r for r in ordered if r.get(key,0)<anchor.get(key,0)];observed=football_replay(prefix,game,game,ctx);owners={p:t for t,v in game['teams'].items() for p in v['players']};teams=[game['home'],game['away']];ledger=FootballLedger(sport,teams,owners);ledger.team={t:Counter(v) for t,v in observed['team'].items()};ledger.players=defaultdict(Counter,{p:Counter(v) for p,v in observed['players'].items()});ledger.verify();prepared,_=(nfl_kernel_rows if sport=='NFL' else cfb_kernel_rows)(rows,game);kernel=PlayKernel(sport,teams,prepared,owners)
        if sport=='CFB':
            from modeling.integration_v22.clock import RuntimeClock,serialize_clock
            kernel.clock_model=RuntimeClock(serialize_clock(pickle.load((ROOT/'artifacts/overnight-v21/clock/censored_drive_em2.pickle').open('rb'))),game['at'])
            from modeling.overnight_v20.data import archives
            k=[r['elapsed'] for r in archives('CFB')['rows'] if r['kind']=='kneel' and r.get('elapsed') is not None and 1<=r['elapsed']<=90 and r['at']<game['at']]
            kernel.positive['kneel']=k
        c=anchor['quarter_seconds_remaining'] if sport=='NFL' else sum(a*b for a,b in zip(map(float,anchor['clock.displayValue'].split(':')),[60,1]));offense=anchor['posteam'] if sport=='NFL' else 'cfb:espn:'+str(int(anchor['pos_team_id']));initial={'ledger':ledger,'period':3,'remaining':c,'offense':offense,'firstReceivingTeam':teams[0],'field':anchor['yardline_100'] if sport=='NFL' else anchor['start.yardsToEndzone'],'down':1,'distance':anchor['ydstogo'] if sport=='NFL' else anchor['distance'],'running':False};extra=[];two=[]
        for r in [r for rs in raw[sport].values() for r in rs]:
            if sport=='NFL':
                if r.get('extra_point_attempt'):extra.append(int(r.get('extra_point_result')=='good'))
                if r.get('two_point_attempt'):two.append(int(r.get('two_point_conv_result')=='success'))
            else:
                if r.get('xp_attempt'):extra.append(int(bool(r.get('xp_made'))))
                if r.get('two_point_conv_result') is not None:two.append(int(r['two_point_conv_result']=='success'))
        result=football_remaining(kernel,ctx,game['season'],initial,8,24024,{'extra_point':extra,'two_point':two});actual_elapsed=1800+900-c
        for r in result['results']:
            if r['simulatedRemainingRegulationSeconds']!=3600-actual_elapsed:raise AssertionError('Past regulation time was simulated again')
            for t in teams:
                for k in ['passingAttempts','carries','receptions']:
                    if r['team'][t].get(k,0)<ledger.team[t][k]:raise AssertionError('Actual accumulated opportunities disappeared')
        result['initialActual']={'scores':{t:ledger.team[t]['points'] for t in teams},'players':{p:dict(v) for p,v in ledger.players.items()},'period':3,'remaining':c,'elapsed':actual_elapsed};freeze_json(OUT/'continuation'/(gid.replace(':','_')+'.json.gz'),compact(result));cases.append({'sport':sport,'gameId':gid,'games':8,'onlyRemainingClockSimulated':True,'actualOpportunitiesRetained':True,'actualElapsed':actual_elapsed,'simulatedRegulationRemaining':3600-actual_elapsed,'scope':'Final-roster-conditioned Mode A continuation, NOT a live forecast/backtest','finalGameRatesUsed':True});details[sport]=result['initialActual']
    from modeling.dynamic_v24.nba_prefix import checkpoint
    gid='nba:espn:401703406';game=packets['NBA'][gid];initial=checkpoint(game,raw['NBA'][gid]);intervals,clocklaw=nba_action_intervals(raw['NBA'][gid]);result=nba_remaining(game,v23.source_context('NBA',gid),initial,8,24024,intervals);elapsed=initial['actualClockElapsed'];ledger=initial['ledger']
    for r in result['results']:
        if abs(r['simulatedRemainingSeconds']-(2880-elapsed+300*r['overtimePeriods']))>1e-6:raise AssertionError('NBA completed game time was simulated twice')
        for p,s in ledger.players.items():
            for k in ('points','rebounds','assists','fieldGoalAttempts','turnovers'):
                if r['players'].get(p,{}).get(k,0)<s[k]:raise AssertionError('Observed NBA count disappeared')
    result['initialActual']={'scores':{t:ledger.team[t]['points'] for t in ledger.teams},'players':{p:dict(s) for p,s in ledger.players.items()},'period':1,'remaining':initial['remaining'],'elapsed':elapsed,'prefixEvents':initial['prefixEvents']};freeze_json(OUT/'continuation'/(gid.replace(':','_')+'.json.gz'),compact(result));cases.append({'sport':'NBA','gameId':gid,'games':8,'onlyRemainingClockSimulated':True,'actualOpportunitiesRetained':True,'actualElapsed':elapsed,'simulatedRegulationRemaining':2880-elapsed,'scope':'Mode A final-rate-conditioned mechanical continuation; not a live forecast','finalGameRatesUsed':True})
    atomic(OUT/'continuation/results.json',{'cases':cases,'strictLiveReplayForecasts':0,'liveBrier':None,'liveLogLoss':None,'latencyCalibration':None,'withheldReason':'No source-arrival-complete historical feed, validated remaining-game model and joint certificate. Mechanical continuations use final-conditioned inputs and are not graded for accuracy.'});return {'mechanicalContinuationGames':sum(c['games'] for c in cases),'strictLiveReplayForecasts':0}
if __name__=='__main__':
    if '--register' in sys.argv:freeze_json(OUT/'specs/continuation-r2.json',{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'modeling/dynamic_v24').glob('*.py'))]},'mode':'historical_mechanics','gamesPerPrefix':8,'pregameOrLiveAccuracyClaims':False})
    else:print(json.dumps(job('continuation-r2',run,cpu=120,wall=300),indent=2))
