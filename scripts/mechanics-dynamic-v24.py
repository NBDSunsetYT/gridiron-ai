"""Exercise only statistically supported event policies through joint ledgers."""
import sys,json,pickle,hashlib,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.policy import FootballPolicyKernel,BasketballPolicy
from modeling.dynamic_v24.football import mechanics_games
from modeling.dynamic_v24.basketball import _complete_games as basketball_games
from modeling.fullgame_v23.forecast import compact
from modeling.fullgame_v23.kernel_inputs import nfl_kernel_rows,cfb_kernel_rows
from modeling.fullgame_v23.timing import nba_action_intervals
from modeling.fullgame_v23.modes import context,Mode
from modeling.overnight_v20.state import atomic,read
from modeling.iterative_learning import freeze_json
spec=importlib.util.spec_from_file_location('v23',ROOT/'scripts/fullgame-v23.py');v23=importlib.util.module_from_spec(spec);spec.loader.exec_module(v23)
spec2=importlib.util.spec_from_file_location('seq24',ROOT/'scripts/sequential-dynamic-v24.py');seq=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(seq)
def run():
    packets,raw=v23.inputs();rows=[]
    for sport,gid in [('NFL','2024_05_BAL_CIN'),('CFB','cfb:espn:401628439')]:
        model=pickle.load((OUT/'sequential'/sport/'0/actions-models.pickle').open('rb'))['B'];game=packets[sport][gid];prepared,_=(nfl_kernel_rows if sport=='NFL' else cfb_kernel_rows)(raw[sport][gid],game);owners={p:t for t,v in game['teams'].items() for p in v['players']};extra=[];two=[]
        for r in [r for rs in raw[sport].values() for r in rs]:
            if sport=='NFL':
                if r.get('extra_point_attempt'):extra.append(int(r.get('extra_point_result')=='good'))
                if r.get('two_point_attempt'):two.append(int(r.get('two_point_conv_result')=='success'))
            else:
                if r.get('xp_attempt'):extra.append(int(bool(r.get('xp_made'))))
                if r.get('two_point_conv_result') is not None:two.append(int(r['two_point_conv_result']=='success'))
        for variant in ('A','B'):
            if (OUT/'dynamic-mechanics'/(sport+'-'+variant+'.json.gz')).exists():
                rows.append({'sport':sport,'eventId':gid,'variant':variant,'games':8,'allJointInvariantsPassed':True,'forecastAccuracyEvaluated':False,'reusedCompletedProtocol':'dynamic-mechanics-r1'});continue
            k=FootballPolicyKernel(sport,[game['home'],game['away']],prepared,owners,event_model=model if variant=='B' else None,validation={'conditionalEventLawAccepted':variant=='B','productionPromotion':False})
            if sport=='CFB':
                from modeling.integration_v22.clock import RuntimeClock,serialize_clock
                from modeling.overnight_v20.data import archives
                k.clock_model=RuntimeClock(serialize_clock(pickle.load((ROOT/'artifacts/overnight-v21/clock/censored_drive_em2.pickle').open('rb'))),game['at']);k.positive['kneel']=[r['elapsed'] for r in archives('CFB')['rows'] if r['kind']=='kneel' and r.get('elapsed') is not None and 1<=r['elapsed']<=90 and r['at']<game['at']]
            result=mechanics_games(k,v23.source_context(sport,gid),game['season'],8,24024,{'extra_point':extra,'two_point':two});freeze_json(OUT/'dynamic-mechanics'/(sport+'-'+variant+'.json.gz'),compact(result));rows.append({'sport':sport,'eventId':gid,'variant':variant,'games':8,'allJointInvariantsPassed':True,'forecastAccuracyEvaluated':False})
    selection=read(OUT/'specs/sequential-r3.json')['selection']['NBA'][0]['validation'];candidate=selection[0];game=v23.data.archives('NBA');game=next(g for g in game.values() if g['id']==candidate['id']);source=seq.load_games('NBA',[candidate]);import pyarrow.parquet as pq
    events=pq.read_table(candidate['path'],filters=[('game_id','=',int(candidate['id'].split(':')[-1]))]).to_pylist();intervals,_=nba_action_intervals(events);source_version=hashlib.sha256(Path(candidate['path']).read_bytes()).hexdigest();ctx=context(Mode.MECHANICS,'NBA',candidate['id'],[{'source':'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_pbp/play_by_play_2025.parquet','sourceVersion':source_version}]);models=pickle.load((OUT/'sequential/NBA/0-identity-r3/actions-models.pickle').open('rb'))
    for variant in ('A','B','B_fatigue'):
        if (OUT/'dynamic-mechanics'/('NBA-'+variant+'.json.gz')).exists():
            rows.append({'sport':'NBA','eventId':candidate['id'],'variant':variant,'games':8,'allJointInvariantsPassed':True,'forecastAccuracyEvaluated':False,'reusedCompletedProtocol':'dynamic-mechanics-r1'});continue
        policy=None if variant=='A' else BasketballPolicy(list(game['teams']),models[variant],{'conditionalEventLawAccepted':True,'scope':'conditional action-law mechanics only'});result=basketball_games(game,ctx,8,24024,intervals,policy=policy);freeze_json(OUT/'dynamic-mechanics'/('NBA-'+variant+'.json.gz'),compact(result));rows.append({'sport':'NBA','eventId':candidate['id'],'variant':variant,'games':8,'allJointInvariantsPassed':True,'forecastAccuracyEvaluated':False})
    atomic(OUT/'dynamic-mechanics/results.json',{'cases':rows,'jointPredictiveSuperiority':False,'C_full_momentum':'Not automatically applied; football momentum and NBA hot-hand evidence did not pass','strictForecasts':0});return {'jointMechanicsGames':sum(r['games'] for r in rows),'strictForecasts':0}
if __name__=='__main__':
    if '--register' in sys.argv:freeze_json(OUT/'specs/dynamic-mechanics-r2.json',{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'modeling/dynamic_v24').glob('*.py'))]},'mode':'historical_mechanics','gamesPerVariant':8,'unsupportedMomentumNotApplied':True,'continuation':'Reuse r1 completed snapshots; repair feedback event actor shadowed by rebound actor'})
    else:print(json.dumps(job('dynamic-mechanics-r2',run,cpu=180,wall=300),indent=2))
