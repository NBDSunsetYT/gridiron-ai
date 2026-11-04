"""Real fixed-cutoff replay, explicitly retrospective; never production accuracy.
Downloads one public nflverse season, streams only the required training columns,
and runs coherent complete games using the unchanged production simulator.
"""
import argparse,csv,gzip,hashlib,io,json,time,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modeling.nflverse_adapter import normalize,number
from modeling.fit import fit_csv
from modeling.simulator import simulate

def run(game_id,count,out):
    season,week,away,home=game_id.split('_');season,week=int(season),int(week)
    schedule_url='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
    schedule_raw=urllib.request.urlopen(schedule_url,timeout=30).read()
    matches=[r for r in csv.DictReader(io.StringIO(schedule_raw.decode())) if r['game_id']==game_id]
    if len(matches)!=1:raise ValueError('Exact historical game identity required')
    game=matches[0]
    if game['home_score']=='' or game['away_score']=='':raise ValueError('A real completed historical game is required')
    from zoneinfo import ZoneInfo
    event=datetime.fromisoformat(game['gameday']+'T'+game['gametime']).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc).isoformat()
    url=f'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz'
    path=Path('/tmp/gridiron-reality-pbp-'+str(season)+'.csv.gz')
    if not path.exists():
        with urllib.request.urlopen(url,timeout=60) as r,path.open('wb') as f:
            while chunk:=r.read(1024*1024):f.write(chunk)
    fields='season_type week posteam defteam play_type no_play penalty extra_point_attempt two_point_attempt sack qb_kneel qb_spike time_of_day down yardline_100 game_id game_half game_seconds_remaining passer_player_id receiver_player_id rusher_player_id complete_pass lateral_reception lateral_rush lateral_return fixed_drive drive field_goal_result extra_point_result two_point_conv_result play_id ydstogo score_differential yards_gained interception fumble_lost kick_distance return_yards epa success air_yards yards_after_catch'.split()
    rows=[]
    with gzip.open(path,'rt',newline='') as f:
        for row in csv.DictReader(f):
            if row.get('season_type')=='REG' and number(row,'week')<week and (row.get('posteam') in (home,away) or row.get('defteam') in (home,away)):
                rows.append({k:row.get(k,'') for k in fields})
    raw,conversion=normalize(rows,week-1);fitted=fit_csv(raw,url+'; nflverse attribution, data license must be independently respected',(datetime.fromisoformat(event)-timedelta(days=1)).isoformat())
    start=time.perf_counter();cpu=time.process_time();result=simulate(fitted['model'],home,away,count,14013,event,representative_games=1);elapsed=time.perf_counter()-start;cpu=time.process_time()-cpu
    created=datetime.now(timezone.utc).isoformat();game_meta={'id':game_id,'sport':'NFL','season':season,'week':week,'startTime':event,'home':{'id':home,'name':home},'away':{'id':away,'name':away}}
    frozen={'schemaVersion':1,'game':game_meta,'analysisId':'historical-'+hashlib.sha256((game_id+str(count)+fitted['model']['sha256']).encode()).hexdigest(),'predictedAt':created,'inputVersion':fitted['model']['sha256'],'modelVersion':result['modelVersion'],'result':result,'research':{'source':url,'collectedAt':created,'historicalPublicationVerified':False,'inputConversion':conversion,'trainingGames':fitted['summary']['games'],'limitations':['Retrospective replay with current historical corrections; original pregame publication and injury availability are not established.','Historical participants and conditional play resampling are baseline evidence, not a validated current personnel forecast.']},'retrospective':True}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(frozen,separators=(',',':')))
    # Local disposable fitted artifact enables exact-statistic replay. It is not
    # uploaded into PostgreSQL or exposed through the public app.
    out.with_suffix('.input.json').write_text(json.dumps(fitted['model'],separators=(',',':')))
    report={'gameId':game_id,'mode':'retrospective','source':url,'sourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'inputVersion':frozen['inputVersion'],'simulations':count,'seed':14013,'seconds':elapsed,'cpuSeconds':cpu,'predictedHome':result['scoreDistributions'][home]['mean'],'predictedAway':result['scoreDistributions'][away]['mean'],'actualHome':int(game['home_score']),'actualAway':int(game['away_score']),'trainingGames':fitted['summary']['games'],'allGamesRetained':False,'representativeGames':len(result.get('representativeGames',[])),'promotion':False,'limitations':frozen['research']['limitations']}
    out.with_suffix('.report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--game',default='2025_13_KC_DAL');p.add_argument('--simulations',type=int,choices=[10000,50000,100000],default=10000);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.game,a.simulations,a.out)
