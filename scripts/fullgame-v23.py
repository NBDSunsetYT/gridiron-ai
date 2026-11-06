"""Bounded Mode A execution. Mode B is audited separately; never inferred from A."""
import sys,json,gzip,pickle,hashlib,types,re
from pathlib import Path
from collections import defaultdict,Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import pyarrow.parquet as pq
from modeling.fullgame_v23.io import OUT,fetch
from modeling.fullgame_v23.runtime import job,verify_parent
from modeling.fullgame_v23.modes import Mode,context
from modeling.fullgame_v23.replay import football_replay,football_book_totals
from modeling.fullgame_v23.nba_replay import replay as nba_replay
from modeling.fullgame_v23.football import PlayKernel,mechanics_games as football_games
from modeling.fullgame_v23.basketball import mechanics_games as nba_games
from modeling.fullgame_v23.gamebook import primary_actions,reconcile
from modeling.fullgame_v23.timing import nba_action_intervals
from modeling.integration_v22.datasets import cfb_packets,protected
from modeling.overnight_v20 import data
from modeling.overnight_v20.state import read,atomic,digest
from modeling.iterative_learning import freeze_json
def unpack(p):return json.loads(gzip.decompress(p.read_bytes()))
SELECTION={'NFL':['2024_05_BAL_CIN','2024_03_JAX_BUF','2024_02_NYG_WAS'],'CFB':['cfb:espn:401635556','cfb:espn:401643793','cfb:espn:401628497','cfb:espn:401628439'],'NBA':['nba:espn:401704791','nba:espn:401703371','nba:espn:401703406','nba:espn:401704740']}
BOOKS={'2024_05_BAL_CIN':'7d40c084-1312-11ef-afd1-646009f18b2e','cfb:espn:401635556':'cfb_espn_401635556','cfb:espn:401643793':'cfb_espn_401643793','cfb:espn:401628497':'cfb_espn_401628497','cfb:espn:401628439':'24FB_GameStats_GaTech','nba:espn:401704791':'20241113_MEMLAL_book','nba:espn:401703371':'20241112_MIADET_book','nba:espn:401703406':'20241126_HOUMIN_book','nba:espn:401704740':'20241106_LALMEM_book'}
def code():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'modeling/fullgame_v23').glob('*.py'))]}
def source_context(sport,gid):
    source=read(OUT/'sources'/('stats_team_week_2024.source.json')) if sport=='NFL' else {'url':'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/'+('espn_cfb_pbp/play_by_play_2024.parquet' if sport=='CFB' else 'espn_nba_pbp/play_by_play_2025.parquet')}
    # Source hashes below are replaced by exact cropped input file checksums;
    # no invented version or publication timestamp qualifies Mode B.
    p=OUT/'sources'/({'NFL':'NFL-selected-raw.json.gz','CFB':'CFB-selected-r2-raw.json.gz','NBA':'NBA-selected-raw.json.gz'}[sport]);src=[{'source':source.get('url'),'sourceVersion':hashlib.sha256(p.read_bytes()).hexdigest(),'role':'owned_replay_observations','publicationTime':'unverified_original'}]
    manifests=read(OUT/'gamebooks/manifest.json',[])+read(ROOT/'artifacts/overnight-v21/gamebooks/manifest.json',[])
    if gid in BOOKS:
        for m in manifests:
            if Path(m['path']).stem==BOOKS[gid]:src.append(m)
    return context(Mode.MECHANICS,sport,gid,src)
def inputs():
    cfb,_=cfb_packets();packets={'CFB':{g['id']:g for g in cfb}};raw_nfl=unpack(OUT/'sources/NFL-selected-raw.json.gz');raw_cfb=unpack(OUT/'sources/CFB-selected-r2-raw.json.gz');raw_nba=unpack(OUT/'sources/NBA-selected-raw.json.gz');nfldata=data.archives('NFL');nba={g['id']:g for g in data.archives('NBA').values()};packets['NBA']=nba
    mapping={'passingAttempts':'attempts','completions':'completions','passingYards':'passing_yards','carries':'carries','rushingYards':'rushing_yards','receptions':'receptions','receivingYards':'receiving_yards'};players=pq.read_table(OUT/'sources/stats_player_week_2024.parquet').to_pylist();teams=pq.read_table(OUT/'sources/stats_team_week_2024.parquet').to_pylist();packets['NFL']={}
    for gid in SELECTION['NFL']:
        g=nfldata['games'][gid];out={'id':gid,'sport':'NFL','at':g['firstObservedAt'],'season':g['season'],'home':g['home'],'away':g['away'],'teams':{}}
        for team in [g['home'],g['away']]:
            pr={r['player_id']:{'stats':{k:float(r[v] or 0) for k,v in mapping.items()},'name':r['player_display_name']} for r in players if r['game_id']==gid and r['team']==team and sum(float(r.get(k) or 0) for k in ('attempts','carries','targets','receptions'))>0};tr=next(r for r in teams if r['game_id']==gid and r['team']==team);totals={k:float(tr[v]) for k,v in mapping.items()};totals.update(score=g['actualHome'] if team==g['home'] else g['actualAway'],offensivePlays=tr['attempts']+tr['carries']+tr['sacks_suffered']);out['teams'][team]={'players':pr,'totals':totals}
        packets['NFL'][gid]=out
    rows={'NFL':defaultdict(list),'CFB':defaultdict(list),'NBA':defaultdict(list)}
    for s,raw in [('NFL',raw_nfl),('CFB',raw_cfb),('NBA',raw_nba)]:
        for r in raw:rows[s][str(r['game_id']) if s=='NFL' else ('cfb:espn:' if s=='CFB' else 'nba:espn:')+str(int(r['game_id']))].append(r)
    return packets,rows
def prepare():
    if (OUT/'protocol.json').exists():raise ValueError('Protocol already frozen')
    assert not set(g for gs in SELECTION.values() for g in gs)&protected();p='/tmp/gridiron-nba-pbp-2025.parquet';ids=[int(g.split(':')[-1]) for g in SELECTION['NBA']];raw=pq.read_table(p,filters=[('game_id','in',ids)]).to_pylist();(OUT/'sources/NBA-selected-raw.json.gz').write_bytes(gzip.compress(json.dumps(raw,default=str).encode()))
    atomic(OUT/'protocol.json',{'version':23,'selection':SELECTION,'books':BOOKS,'mode':'historical_mechanics','seed':23001,'gamesPerConditionalMechanicsMatchup':16,'forecastComparisonsAllowed':False,'strictPregameRequirementUnchanged':True,'protectedIds':sorted(protected()),'objectives':'Replay official boxes/books, exercise generated full-game clocks/possessions/accounting; no accuracy optimization or sealed-final grading','numericCode':code(),'sourceVersions':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'sources').glob('*') if p.is_file()}});print('Registered',sum(map(len,SELECTION.values())),'Mode A matchups')
def replay_all(revision='r8'):
    packets,rows=inputs();summary={};folder=OUT/('replay-'+revision);folder.mkdir(exist_ok=True)
    for sport in ['NFL','CFB','NBA']:
        report=[]
        for gid in SELECTION[sport]:
            try:
                game=packets[sport][gid];ctx=source_context(sport,gid);book=(OUT/'gamebooks'/(BOOKS.get(gid,'missing')+'.txt'))
                if sport=='NBA':r=nba_replay(game,rows[sport][gid],book.read_text(),ctx)
                else:
                    resolved=rows[sport][gid];corrections=None
                    if sport=='CFB' and book.exists() and max(int(r['period']) for r in resolved)<=4:
                        labels={'cfb:espn:401635556':({'jamesmadison':game['away'],'northcarolina':game['home']},{'JMU':game['away'],'UNC':game['home']}),'cfb:espn:401643793':({'ballst':game['away'],'ballstate':game['away'],'jamesmadison':game['home']},{'BSU':game['away'],'JMU':game['home']}),'cfb:espn:401628497':({'minnesota':game['away'],'michigan':game['home']},{'MIN':game['away'],'UoM':game['home']}),'cfb:espn:401628439':({'georgiatech':game['away'],'georgia':game['home']},{'GT':game['away'],'UGA':game['home']})}
                        names,codes=labels[gid];acts=primary_actions(book.read_text(),names,codes);resolved,corrections=reconcile(rows[sport][gid],acts,ctx['sources'][-1],{t:v['players'] for t,v in game['teams'].items()});freeze_json(folder/(gid.replace(':','_')+'-primary-accounting.json.gz'),{'primaryActions':acts,'reconciliation':corrections});
                    r=football_replay(resolved,game,game,ctx)
                    if corrections:r['primaryReconciliation']={k:len(v) if isinstance(v,list) else v for k,v in corrections.items()}
                    if book.exists():
                        ref=football_book_totals(book.read_text(),sport,[game['away'],game['home']]);r['independentGamebookComparisons']=[{'team':t,'stat':stat,'official':v,'replayed':r['team'][t].get(stat,0),'equal':v==r['team'][t].get(stat,0)} for stat,vals in ref.items() for t,v in vals.items()];r['independentGamebookAllEqual']=all(x['equal'] for x in r['independentGamebookComparisons'])
                freeze_json(folder/(gid.replace(':','_')+'.json.gz'),r);report.append({k:v for k,v in r.items() if k not in ('players','team','scoringEvents','statComparisons','playerComparisons','researchContext','minutes')});print(json.dumps({'league':sport,'game':gid,'teamStats':r.get('teamAccountingReconciled',r.get('allPlayerStatsReconciled')),'scores':r['scoreReconciled'],'rejected':len(r.get('rejectedPlays',r.get('unresolvedEvents',[])))}),flush=True)
            except Exception as e:report.append({'gameId':gid,'error':type(e).__name__,'reason':str(e)});print(json.dumps({'league':sport,'game':gid,'error':str(e)}),flush=True)
        summary[sport]=report
    atomic(folder/'results.json',summary);return {'mode':'historical_mechanics','matchupsAttempted':{s:len(v) for s,v in summary.items()},'accuracyMetricsComputed':False}
def simulate_all(revision='r1',trials=16):
    packets,raw=inputs();folder=OUT/('simulated-mechanics-'+revision);folder.mkdir(exist_ok=True);results=[];sources={s:data.archives(s)['rows'] for s in ['NFL','CFB']};qualified=[];banned=protected()
    from modeling.integration_v22.clock import RuntimeClock,serialize_clock
    clock=pickle.load((ROOT/'artifacts/overnight-v21/clock/censored_drive_em2.pickle').open('rb'))
    for sport in ['NFL','CFB','NBA']:
        for gi,gid in enumerate(SELECTION[sport]):
            replay_path=OUT/'replay-r8'/(gid.replace(':','_')+'.json.gz');replayed=unpack(replay_path) if replay_path.exists() else None
            # Source-incomplete cases do not acquire an invented eligibility.
            if not replayed or not replayed['completeAccountingReplay']:
                results.append({'gameId':gid,'sport':sport,'status':'source_replay_blocked','reason':'Independent player/team accounting replay incomplete'});continue
            game=packets[sport][gid];ctx=source_context(sport,gid)
            try:
                if sport=='NBA':
                    intervals,law=nba_action_intervals(raw[sport][gid]);r=nba_games(game,ctx,trials,23001+gi,intervals);r['clockSourceDiagnostics']=law
                else:
                    teams=[game['home'],game['away']];owners={p:t for t,v in game['teams'].items() for p in v['players']};rows=[r for r in sources[sport] if r['game']==gid];at=game.get('at',data.archives(sport)['games'][gid]['firstObservedAt']);timing=RuntimeClock(serialize_clock(clock),at) if sport=='CFB' else None;clock_pools={}
                    if sport=='CFB':clock_pools['kneel']=[int(r['elapsed']) for r in sources[sport] if r['kind']=='kneel' and r['game'] not in banned and r['at']<at and r.get('elapsed') is not None and 1<=r['elapsed']<=90]
                    kernel=PlayKernel(sport,teams,rows,owners,timing,clock_pools);extra=[];two=[]
                    for rs in raw[sport].values():
                        for e in rs:
                            if sport=='NFL':
                                if e.get('extra_point_attempt'):extra.append(int(e.get('extra_point_result')=='good'))
                                if e.get('two_point_attempt'):two.append(int(e.get('two_point_conv_result')=='success'))
                            else:
                                if e.get('xp_attempt'):extra.append(int(bool(e.get('xp_made'))))
                                if e.get('two_point_conv_result') is not None:two.append(int(e['two_point_conv_result']=='success'))
                    r=football_games(kernel,ctx,game['season'],trials,23001+gi,{'extra_point':extra,'two_point':two});r['conversionEvidenceCounts']={'extraPointAttempts':len(extra),'twoPointAttempts':len(two)}
                freeze_json(folder/(gid.replace(':','_')+'.json.gz'),r);record={'sport':sport,'gameId':gid,'status':'completed','completeConditionalMechanicsGames':len(r['results']),'seed':r['seed'],'overtimeGames':sum(x['overtimePeriods']>0 for x in r['results']),'scoresObservedInGeneratedTrials':{t:[min(x['scores'][t] for x in r['results']),max(x['scores'][t] for x in r['results'])] for t in r['results'][0]['scores']},'allInvariantsPassed':r['mechanicalInvariantsPassed'],'notAPregamePrediction':True};results.append(record);print(json.dumps(record),flush=True)
            except Exception as e:results.append({'sport':sport,'gameId':gid,'status':'failed','error':type(e).__name__,'reason':str(e)});print(json.dumps(results[-1]),flush=True)
    atomic(folder/'results.json',{'mode':'historical_mechanics','cases':results,'newPregameForecastTrials':0,'accuracyMetricsComputed':False});return {'cases':results,'newPregameForecastTrials':0}
if __name__=='__main__':
    if '--prepare' in sys.argv:prepare()
    elif '--probe' in sys.argv:print(replay_all())
    elif '--simulate' in sys.argv:print(simulate_all())
    else:raise SystemExit('Use --prepare, --probe or --simulate')
