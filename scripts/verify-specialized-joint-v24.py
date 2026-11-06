"""Mode A joint adapter verification on owned official historical inputs.

Final-conditioned source rates/participants are permitted here and prominently
labeled. They are never used to grade pregame predictions or establish accuracy.
"""
import sys,json,hashlib,pickle,importlib.util
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.football import PlayKernel,mechanics_games
from modeling.dynamic_v24 import basketball
from modeling.dynamic_v24.completion.joint import HeadFootballKernel,football_mechanics,nba_rates,nba_mechanics
from modeling.dynamic_v24.completion.data import packets,enrich_packets
from modeling.dynamic_v24.completion.efficient_data import records
from modeling.fullgame_v23.kernel_inputs import nfl_kernel_rows,cfb_kernel_rows
from modeling.fullgame_v23.timing import nba_action_intervals
from modeling.fullgame_v23.forecast import compact
from modeling.fullgame_v23.accounting import team_actor
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import read,atomic
spec=importlib.util.spec_from_file_location('v23',ROOT/'scripts/fullgame-v23.py');v23=importlib.util.module_from_spec(spec);spec.loader.exec_module(v23)
DEST=OUT/'specialized-joint-mechanics-r1'

def run():
    owned,raw=v23.inputs();cases=[];histories={}
    for sport,ids in v23.SELECTION.items():
        latest=max(g.get('at') or g.get('firstObservedAt') for key,g in owned[sport].items() if key in ids)
        gs=enrich_packets([g for g in packets(sport) if g['at']<=latest],sport);rr=records(gs,sport,set(ids));histories[sport]={(r['gameId'],r['player'],r['stat']):r['baseline'] for r in rr if r['player']!='__team__'}
        for gid in ids:
            game=owned[sport][gid];ctx=v23.source_context(sport,gid)
            for variant in ['event_reference','box_head_adapter','lagged_head_adapter']:
                try:
                    if sport=='NBA':
                        intervals,_=nba_action_intervals(raw[sport][gid]);est={}
                        for p in game['players']:
                            if float(p.get('minutes') or 0)<=0:continue
                            pid=str(int(p['athlete_id']));values={'minutes':float(p['minutes']),'fieldGoalAttempts':float(p['field_goals_attempted']),'threePointAttempts':float(p['three_point_field_goals_attempted']),'freeThrowAttempts':float(p['free_throws_attempted']),'rebounds':float(p['offensive_rebounds']+p['defensive_rebounds']),'assists':float(p['assists'])}
                            if float(p.get('points') or 0)>0:values['points']=float(p['points'])
                            est[pid]=values
                        injected=0
                        if variant=='lagged_head_adapter':
                            for pid,values in est.items():
                                for stat in list(values):
                                    key=(gid,pid,stat)
                                    if key in histories[sport]:values[stat]=histories[sport][key];injected+=1
                        adapted=game if variant=='event_reference' else nba_rates(game,est,{'sport':sport,'estimand':'conditional_mean','modelVersions':['box-head-mechanics' if variant=='box_head_adapter' else 'rolling5-lagged-history'],'finalConditionedFallback':True},ctx)
                        result=basketball.mechanics_games(adapted,ctx,4,240244,intervals) if variant=='event_reference' else nba_mechanics(adapted,ctx,games=4,seed=240244,clock_intervals=intervals)
                    else:
                        teams=[game['home'],game['away']];owners={p:t for t,v in game['teams'].items() for p in v['players']};prepared,_=(nfl_kernel_rows if sport=='NFL' else cfb_kernel_rows)(raw[sport][gid],game);est={p:{k:float(x) for k,x in v['stats'].items() if k in ['passingAttempts','passingYards','carries','rushingYards','receptions','receivingYards']} for t,team in game['teams'].items() for p,v in team['players'].items()};est={p:v for p,v in est.items() if v};injected=0
                        for t,team in game['teams'].items():
                            credits={k:float(v) for k,v in team.get('unassignedTeamCredits',{}).items() if k in ['passingAttempts','passingYards','carries','rushingYards','receptions','receivingYards']}
                            if credits:owners[team_actor(t)]=t;est[team_actor(t)]=credits
                        if variant=='lagged_head_adapter':
                            for pid,values in est.items():
                                for stat in list(values):
                                    key=(gid,pid,stat)
                                    if key in histories[sport]:values[stat]=histories[sport][key];injected+=1
                        kwargs={}
                        if sport=='CFB':
                            from modeling.integration_v22.clock import RuntimeClock,serialize_clock
                            from modeling.overnight_v20.data import archives
                            kwargs['clock_model']=RuntimeClock(serialize_clock(pickle.load((ROOT/'artifacts/overnight-v21/clock/censored_drive_em2.pickle').open('rb'))),game['at']);kwargs['additional_clock_pools']={'kneel':[r['elapsed'] for r in archives('CFB')['rows'] if r['kind']=='kneel' and r.get('elapsed') is not None and 1<=r['elapsed']<=90 and r['at']<game['at']]}
                        kernel=PlayKernel(sport,teams,prepared,owners,**kwargs) if variant=='event_reference' else HeadFootballKernel(sport,teams,prepared,owners,estimates=est,head_manifest={'sport':sport,'estimand':'conditional_mean','modelVersions':['box-head-mechanics' if variant=='box_head_adapter' else 'rolling5-lagged-history'],'finalConditionedFallback':True},**kwargs)
                        extra=[];two=[]
                        for rs in raw[sport].values():
                            for e in rs:
                                if sport=='NFL':
                                    if e.get('extra_point_attempt'):extra.append(int(e.get('extra_point_result')=='good'))
                                    if e.get('two_point_attempt'):two.append(int(e.get('two_point_conv_result')=='success'))
                                else:
                                    if e.get('xp_attempt'):extra.append(int(bool(e.get('xp_made'))))
                                    if e.get('two_point_conv_result') is not None:two.append(int(e['two_point_conv_result']=='success'))
                        conversions={'extra_point':extra,'two_point':two};result=mechanics_games(kernel,ctx,game['season'],4,240244,conversions) if variant=='event_reference' else football_mechanics(kernel,ctx,game['season'],games=4,seed=240244,conversions=conversions)
                    freeze_json(DEST/sport/(gid.replace(':','_')+'-'+variant+'.json.gz'),compact(result));cases.append({'sport':sport,'gameId':gid,'variant':variant,'status':'passed','games':4,'laggedHeadValuesInjected':injected,'allAccountingChecksPassed':True,'forecastAccuracyEvaluated':False,'finalConditionedFallback':True})
                except (ValueError,AssertionError,KeyError) as e:cases.append({'sport':sport,'gameId':gid,'variant':variant,'status':'withheld','reason':str(e),'games':0,'forecastAccuracyEvaluated':False})
                print(json.dumps(cases[-1]),flush=True)
    atomic(DEST/'results.json',{'cases':cases,'mode':'historical_mechanics','newStrictForecasts':0,'jointPredictiveSuperiority':False,'headVersions':'Baseline adapters, not production or probability champion promotion'});return {'completedGames':sum(r['games'] for r in cases),'passedCases':sum(r['status']=='passed' for r in cases),'withheldCases':sum(r['status']=='withheld' for r in cases),'strictForecasts':0}

if __name__=='__main__':
    if '--register' in sys.argv:
        code={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'modeling/dynamic_v24/completion').glob('*.py'))]};freeze_json(OUT/'specs/specialized-joint-r1.json',{'numericCode':code,'mode':'historical_mechanics','gamesPerCase':4,'selection':v23.SELECTION,'accuracyClaimAllowed':False})
    else:print(json.dumps(job('specialized-joint-r1',run,cpu=180,wall=300),indent=2))
