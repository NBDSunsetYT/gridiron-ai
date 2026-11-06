"""Primary-book overtime sequences, plus bounded coverage of NBA generated OT."""
import sys,re,importlib.util,hashlib,json
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.fullgame_v23.io import OUT
from modeling.fullgame_v23.runtime import job
from modeling.fullgame_v23.rules import FootballOvertime
from modeling.fullgame_v23.basketball import mechanics_games
from modeling.fullgame_v23.timing import nba_action_intervals
from modeling.fullgame_v23.forecast import compact
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import atomic
spec=importlib.util.spec_from_file_location('r23',ROOT/'scripts/fullgame-v23.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

def cfb_turns(text):
    """Read the printed OT PBP; merge administrative restarts, not possessions."""
    groups=[];period=0;team=None;lines=[]
    def finish():
        nonlocal lines
        if period and team and lines:groups.append({'period':period,'team':team,'statement':' '.join(lines)})
        lines=[]
    for line in text.splitlines():
        q=re.fullmatch(r'\s*Overtime ([1-8])\s*',line)
        if q:finish();period=int(q[1]);team=None;continue
        if period and 'Quickie report' in line:finish();break
        d=re.match(r'^\s*(Georgia Tech|Georgia) drive starts at',line)
        if period and d:finish();team=d[1];continue
        if period and team:lines.append(line.strip())
    turns=[];administrative=[]
    for g in groups:
        statement=g['statement'];points=6*len(re.findall(r'\bTOUCHDOWN\b',statement))+len(re.findall(r'kick attempt good',statement,re.I))+2*len(re.findall(r'(?:rush|pass) attempt Successful',statement,re.I));valid_try=bool(re.search(r'(?:rush|pass) attempt (?:Successful|failed)',statement,re.I)) and not re.search(r'\bNO\s+PLAY\b',statement)
        if g['period']>=3 and not valid_try:administrative.append(g);continue
        turns.append(g|{'points':points,'elapsedSeconds':0})
    if len(turns)!=16:raise ValueError('Expected one independently printed valid turn per team per OT; incomplete/ambiguous book')
    return turns,administrative

def run():
    packets,raw=s.inputs();text=(OUT/'gamebooks/24FB_GameStats_GaTech.txt').read_text();turns,admin=cfb_turns(text);ot=FootballOvertime('CFB',2024,first=0);teams=['Georgia','Georgia Tech'];sequence=[]
    for turn in turns:
        side=teams.index(turn['team'])
        if ot.period!=turn['period']:raise AssertionError('Printed overtime period disagrees with rule controller')
        ot.finish_possession(side,turn['points']);sequence.append({'period':turn['period'],'team':turn['team'],'points':turn['points'],'clockSeconds':0,'finished':ot.finished})
    if not ot.finished or ot.period!=8 or ot.score!=[17,15]:raise AssertionError('Primary eight-OT score/termination mismatch')
    gid='2024_05_BAL_CIN';rows=sorted([r for r in raw['NFL'][gid] if r.get('qtr')==5],key=lambda r:r['play_id']);groups=defaultdict(list)
    for row in rows:
        if row.get('posteam') in ('BAL','CIN') and row.get('fixed_drive') is not None:groups[(row['fixed_drive'],row['posteam'])].append(row)
    drives=[(k,rs) for k,rs in groups.items() if any(r.get('play_type') in ('run','pass','field_goal','punt') for r in rs)];nfl=FootballOvertime('NFL',2024,first=0);nflseq=[]
    for i,((drive,team),rs) in enumerate(drives):
        start=rs[0]['quarter_seconds_remaining'];end=drives[i+1][1][0]['quarter_seconds_remaining'] if i+1<len(drives) else min(r['quarter_seconds_remaining'] for r in rows if r.get('quarter_seconds_remaining') is not None);points=3*sum(r.get('field_goal_result')=='made' for r in rs)+6*sum(bool(r.get('touchdown')) and r.get('td_team')==team for r in rs);elapsed=start-end;nfl.finish_possession(['BAL','CIN'].index(team),points,elapsed);nflseq.append({'driveId':drive,'team':team,'points':points,'elapsedSeconds':elapsed,'finished':nfl.finished})
    if not nfl.finished or nfl.score!=[3,0]:raise AssertionError('NFL verified overtime possession sequence differs')
    gid=s.SELECTION['NBA'][0];game=packets['NBA'][gid];ctx=s.source_context('NBA',gid);intervals,law=nba_action_intervals(raw['NBA'][gid]);generated=None;count=0
    for seed in range(24000,24096):
        r=mechanics_games(game,ctx,1,seed,intervals);count+=1
        if r['results'][0]['overtimePeriods']:
            generated=compact(r);break
    if generated:freeze_json(OUT/'overtime/generated-nba-ot-r2.json.gz',generated)
    result={'mode':'historical_mechanics','cfb':{'eventId':'cfb:espn:401628439','primaryTurns':sequence,'administrativeRestartFragmentsNotCountedAsPossessions':len(admin),'source':s.source_context('CFB','cfb:espn:401628439')['sources'][-1],'scoreDeltaFromPrimaryBook':ot.score,'allShootoutsUntimed':True,'ordinaryStatsOnShootoutAttempts':False},'nfl':{'eventId':'2024_05_BAL_CIN','possessions':nflseq,'scoreDelta':nfl.score,'remainingSeconds':nfl.remaining,'source':s.source_context('NFL','2024_05_BAL_CIN')['sources'][-1]},'nbaGeneratedCoverage':{'conditionalMatchup':gid,'gamesExecuted':count,'firstOvertimeFound':generated is not None,'seed':generated['seed'] if generated else None,'stoppingRule':'First generated OT or 96 complete mechanical games; never an accuracy criterion'},'pregameForecastTrials':0,'productionWrites':0};atomic(OUT/'overtime/validation-r2.json',result);return {'cfbPrimaryOvertimeTurns':len(turns),'nflPrimaryOvertimePossessions':len(nflseq),'nbaConditionalGamesExecuted':count,'nbaGeneratedOT':generated is not None,'pregameForecastTrials':0}
if __name__=='__main__':
    if '--register' in sys.argv:freeze_json(OUT/'specs/overtime-r2.json',{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'modeling/fullgame_v23').glob('*.py'))]},'mechanicalOnly':True,'maximumAdditionalGames':96,'seeds':[24000,24095],'noScoreTuning':True})
    else:print(json.dumps(job('overtime-r2',run,cpu=120,wall=300),indent=2))
