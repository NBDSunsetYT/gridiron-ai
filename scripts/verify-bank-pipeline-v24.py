"""Automatic frozen-bank -> shared-event mechanics, never forecast accuracy."""
import sys,json,hashlib,pickle,importlib.util
from pathlib import Path
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pyarrow.parquet as pq
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.completion.bank import HeadBank,football_from_bank,nba_from_bank
from modeling.dynamic_v24.completion.data import packets,enrich_packets,features_only
from modeling.dynamic_v24.completion.efficient_data import records
from modeling.fullgame_v23.kernel_inputs import nfl_kernel_rows,cfb_kernel_rows
from modeling.fullgame_v23.timing import nba_action_intervals
from modeling.fullgame_v23.modes import context,Mode
from modeling.fullgame_v23.forecast import compact
from modeling.integration_v22.clock import RuntimeClock,serialize_clock
from modeling.accuracy_v20.quality import aware
from modeling.overnight_v20.data import archives
from modeling.overnight_v20.state import read,atomic
from modeling.iterative_learning import freeze_json
spec=importlib.util.spec_from_file_location('v23',ROOT/'scripts/fullgame-v23.py');v23=importlib.util.module_from_spec(spec);spec.loader.exec_module(v23)
DEST=OUT/'bank-pipeline-r2'
def selection():
    result={'NFL':list(v23.SELECTION['NFL'])}
    for sport,folder in [('CFB','completion-cfb-extension-r1'),('NBA','completion-nba-clean-r1')]:
        ids=set(read(OUT/folder/'protocol.json')['selection'][sport][1]['games']);result[sport]=[g['id'] for g in sorted(packets(sport),key=lambda g:g['at']) if g['id'] in ids][:3]
    return result
def run():
    bank=HeadBank(OUT/'completion-final/bank.json',ROOT);chosen=read(OUT/'specs/bank-pipeline-r2.json')['selection'];prior=read(OUT/'bank-pipeline-r1/results.json',{}).get('cases',[]);owned,old_raw=({},{});out=[]
    for sport,ids in chosen.items():
        if sport!='NBA' and prior:
            out.extend({**c,'reusedCompletedArtifact':True} for c in prior if c['sport']==sport);continue
        gs=packets(sport);bad={r['gameId'] for r in read(OUT/'completion-nba-clean-r1/protocol.json')['sourceRejectedGames']} if sport=='NBA' else set();gs=[g for g in gs if g['id'] not in bad];last=max(g['at'] for g in gs if g['id'] in ids);gs=enrich_packets([g for g in gs if g['at']<=last],sport);frames=records(gs,sport,set(ids));games={g['id']:g for g in gs}
        for gid in ids:
            try:
                game=games[gid];as_of=(aware(game['at'])-timedelta(minutes=30)).isoformat();x=features_only([r for r in frames if r['gameId']==gid]);bundle=bank.bundle(sport,x,as_of,context(Mode.MECHANICS,sport,gid,[{'source':'https://github.com/nflverse/nflverse-data' if sport=='NFL' else 'https://github.com/sportsdataverse/sportsdataverse-data','sourceVersion':bank.manifest['sha256']}]))
                if sport=='NBA':
                    base={g['id']:g for g in archives('NBA').values()}[gid];path=Path('/tmp/gridiron-nba-pbp-2026.parquet');raw=pq.read_table(path,filters=[('game_id','=',int(gid.split(':')[-1]))]).to_pylist();intervals,_=nba_action_intervals(raw);ctx=context(Mode.MECHANICS,sport,gid,[{'source':'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_pbp/play_by_play_2026.parquet','sourceVersion':hashlib.sha256(path.read_bytes()).hexdigest()}]);result=nba_from_bank(bank,x,as_of,ctx,base,games=4,clock_intervals=intervals)
                else:
                    kwargs={};conversion=[];two=[]
                    if sport=='NFL':base=owned[sport][gid];raw=old_raw[sport][gid];ctx=v23.source_context(sport,gid)
                    else:
                        base=game;path=Path('/tmp/gridiron-cfb-public-pbp-2026.parquet');raw=pq.read_table(path,filters=[('game_id','=',int(gid.split(':')[-1]))]).to_pylist();ctx=context(Mode.MECHANICS,sport,gid,[{'source':'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_pbp/play_by_play_2026.parquet','sourceVersion':hashlib.sha256(path.read_bytes()).hexdigest()}]);kwargs['clock_model']=RuntimeClock(serialize_clock(pickle.load((ROOT/'artifacts/overnight-v21/clock/censored_drive_em2.pickle').open('rb'))),game['at']);kwargs['additional_clock_pools']={'kneel':[r['elapsed'] for r in archives('CFB')['rows'] if r['kind']=='kneel' and r.get('elapsed') is not None and 1<=r['elapsed']<=90 and r['at']<game['at']]}
                    prepared,_=(nfl_kernel_rows if sport=='NFL' else cfb_kernel_rows)(raw,base);owners={p:t for t,team in base['teams'].items() for p in team['players']}
                    for event in raw:
                        if sport=='NFL':
                            if event.get('extra_point_attempt'):conversion.append(int(event.get('extra_point_result')=='good'))
                            if event.get('two_point_attempt'):two.append(int(event.get('two_point_conv_result')=='success'))
                        else:
                            if event.get('xp_attempt'):conversion.append(int(bool(event.get('xp_made'))))
                            if event.get('two_point_conv_result') is not None:two.append(int(event['two_point_conv_result']=='success'))
                    # Conversions need sourced support. If this game contains no
                    # two-point try, reuse only already observed same-league raw
                    # conversion records, explicitly Mode A and not a forecast.
                    if not two:
                        for values in old_raw[sport].values():
                            for e in values:
                                if sport=='NFL' and e.get('two_point_attempt'):two.append(int(e.get('two_point_conv_result')=='success'))
                                elif sport=='CFB' and e.get('two_point_conv_result') is not None:two.append(int(e['two_point_conv_result']=='success'))
                    result=football_from_bank(bank,sport,x,as_of,ctx,[base['home'],base['away']],prepared,owners,base['season'],games=4,conversions={'extra_point':conversion,'two_point':two},**kwargs)
                freeze_json(DEST/(gid.replace(':','_')+'.json.gz'),compact(result));out.append({'sport':sport,'gameId':gid,'status':'passed','games':4,'selectedHeads':bundle['manifest']['heads'],'allJointInvariantsPassed':True,'tier':'final_roster_conditioned_mechanics','forecastAccuracyEvaluated':False})
            except (ValueError,AssertionError,KeyError,FileNotFoundError) as e:out.append({'sport':sport,'gameId':gid,'status':'withheld','games':0,'reason':str(e),'forecastAccuracyEvaluated':False})
            print(json.dumps(out[-1]),flush=True)
    atomic(DEST/'results.json',{'cases':out,'strictPregameForecasts':0,'productionPromotion':False,'automaticBankConnectionTested':True,'repair':'Archive dictionary keys are not canonical event IDs; exact canonical g.id index replaces direct key lookup'});return {'passedCases':sum(c['status']=='passed' for c in out),'withheldCases':sum(c['status']=='withheld' for c in out),'newMechanicalGames':sum(c['games'] for c in out if not c.get('reusedCompletedArtifact')),'previousGamesReusedWithoutRerun':sum(c['games'] for c in out if c.get('reusedCompletedArtifact')),'strictPregameForecasts':0}
if __name__=='__main__':
    if '--register' in sys.argv:freeze_json(OUT/'specs/bank-pipeline-r2.json',{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'modeling/dynamic_v24/completion').glob('*.py'))]},'inputHashes':{'artifacts/dynamic-v24/completion-final/bank.json':hashlib.sha256((OUT/'completion-final/bank.json').read_bytes()).hexdigest()},'selection':read(OUT/'specs/bank-pipeline-r1.json')['selection'],'gamesPerCase':4,'mode':'historical_mechanics','sourceFinalRosterConditioned':True,'reuseCompletedNFLAndCFB':True})
    else:print(json.dumps(job('bank-pipeline-r2',run,cpu=120,wall=180),indent=2))
