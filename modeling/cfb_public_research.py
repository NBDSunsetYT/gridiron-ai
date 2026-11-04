"""Bounded automatic CFB research from public ESPN-derived release assets.

The publisher distributes these files from its MIT-licensed repository. This
adapter does not call a protected CollegeFootballData endpoint or infer missing
player identities from text. Publication availability is unknown, so the output
is a conditional research baseline, not prospective calibration evidence.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import tempfile
import threading
import time
import urllib.request
from collections import Counter, OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .cfb_simulator import fit_cfb_csv, simulate_cfb, ENGINE_VERSION, MODEL_VERSION
from .fit import REQUIRED, utc

SOURCE_REPOSITORY='https://github.com/sportsdataverse/sportsdataverse-data'
SOURCE_RELEASE=SOURCE_REPOSITORY+'/releases/tag/espn_cfb_pbp'
SOURCE_LICENSE='https://github.com/sportsdataverse/sportsdataverse-data/blob/main/LICENSE'
MAX_SOURCE_BYTES=80_000_000
SOURCE_CACHE_SECONDS=6*3600
_cache_lock=threading.Lock()
_source_cache=None
_season_sources={}
_prepared_cache=None
_prepared_games=OrderedDict()


class CFBSourceUnavailable(RuntimeError):
    """Transport failure is not an empty schedule or an inadequate model."""

COLUMNS=['season','game_id','id','pos_team_id','def_pos_team_id','pos_team','def_pos_team',
         'wallclock','status_type_completed','period','down','distance','start.yardsToEndzone',
         'start.adj_TimeSecsRem','end.adj_TimeSecsRem','start.pos_score_diff','type.text',
         'end.pos_team.id','end.yard',
         'yds_rushed','yds_receiving','yds_sacked','statYardage','air_yards','passer_player_id',
         'receiver_player_id','rusher_player_id','passer_player_name','receiver_player_name',
         'rusher_player_name','xp_attempt','xp_made','two_point_conv_result',
         'defensive_two_point_conv','fg_made','fg_attempt','pass_attempt','sack','completion',
         'int','pos_fumble_lost','yds_punted','yds_punt_return','yds_int_return','yds_fumble_return',
         'offense_score_play','defense_score_play','td_play',
         'punt','rush','kneel_down','penalty_no_play','penalty_negated_play','penalty_flag',
         'drive.id','drive_play_index','EPA','EPA_success']


def _integer(value, lower=None, upper=None):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or int(value)!=value:
        raise ValueError('A source integer is unavailable')
    value=int(value)
    if lower is not None and value<lower or upper is not None and value>upper:
        raise ValueError('A source integer is outside supported bounds')
    return value


def _id(value):
    if isinstance(value,str) and value.isdigit():return str(int(value))
    return str(_integer(value,1))


def source_file(season):
    """One bounded disk asset, with fixed HTTPS host/path and retained SHA256."""
    global _source_cache
    now=time.monotonic()
    with _cache_lock:
        cached=_season_sources.get(season)
        if cached and now<cached['until'] and Path(cached['path']).is_file():return dict(cached)
        url=f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_pbp/play_by_play_{season}.parquet'
        path=Path(tempfile.gettempdir())/f'gridiron-cfb-public-pbp-{season}.parquet'
        partial=path.with_suffix('.partial')
        digest=hashlib.sha256();size=0
        try:
            request=urllib.request.Request(url,headers={'Accept':'application/octet-stream','User-Agent':'GRIDIRON-AI-CFB-Research/8.0'})
            with urllib.request.urlopen(request,timeout=45) as response, partial.open('wb') as output:
                declared=response.headers.get('Content-Length')
                if declared and int(declared)>MAX_SOURCE_BYTES:
                    raise ValueError('CFB source exceeds the bounded worker download size')
                while chunk:=response.read(1_048_576):
                    size+=len(chunk)
                    if size>MAX_SOURCE_BYTES:raise ValueError('CFB source exceeds the bounded worker download size')
                    digest.update(chunk);output.write(chunk)
            os.replace(partial,path)
        except Exception:
            partial.unlink(missing_ok=True)
            raise CFBSourceUnavailable('The fixed public CFB historical source could not be retrieved; no replacement plays were invented') from None
        _source_cache={'season':season,'path':str(path),'sha256':digest.hexdigest(),'bytes':size,
                       'url':url,'collectedAt':datetime.now(timezone.utc).isoformat(),
                       'availableAt':None,'until':now+SOURCE_CACHE_SECONDS}
        _season_sources[season]=dict(_source_cache)
        return dict(_source_cache)


def normalize_public_cfb(path, home_espn_id, away_espn_id, before, maximum_team_plays=12000):
    """Read selected columns, then only selected teams plus actual league tries."""
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    source=pq.ParquetFile(path)
    required=set(COLUMNS)-{'EPA','EPA_success','air_yards','yds_punt_return','penalty_flag'}
    if not required.issubset(source.schema.names):
        raise ValueError('The published CFB play schema changed; its identities and event definitions need verification')
    wanted=__import__('pyarrow').array([int(home_espn_id),int(away_espn_id)])
    rows=[]
    # Physical row order and the exact predicate are unchanged. Bound Arrow RAM.
    for batch in source.iter_batches(batch_size=16384,columns=[name for name in COLUMNS if name in source.schema.names]):
        table=__import__('pyarrow').Table.from_batches([batch])
        selected=pc.or_kleene(pc.or_kleene(pc.is_in(table['pos_team_id'],value_set=wanted),pc.and_kleene(pc.is_in(table['def_pos_team_id'],value_set=wanted),pc.equal(table['defense_score_play'],True))),pc.is_valid(table['two_point_conv_result']))
        rows.extend(table.filter(selected).to_pylist())
    del table,source
    cutoff=utc(before);output=[];counts=Counter();seen_drives=set();catalog={};latest={};played=[]
    for raw in rows:
        team=str(raw.get('pos_team_id'))
        selected_team=team in (home_espn_id,away_espn_id)
        if raw.get('status_type_completed') is not True:
            counts['incomplete_game']+=1;continue
        try:
            event=utc(raw.get('wallclock'))
        except ValueError:
            counts['missing_event_clock']+=1;continue
        if event>=cutoff:
            counts['at_or_after_cutoff']+=1;continue
        if raw.get('defensive_two_point_conv'):
            counts['unsupported_defensive_try']+=1;continue
        try:
            team_id,defense_id=_id(raw.get('pos_team_id')),_id(raw.get('def_pos_team_id'))
            game_id,play_id=_id(raw.get('game_id')),_id(raw.get('id'))
            full_clock=_integer(raw.get('start.adj_TimeSecsRem'),0,3600)
            base={'sport':'CFB','game_id':'cfb:espn:'+game_id,'play_id':'cfb:espn:'+play_id,
                  'played_at':event.isoformat(),'offense':'cfb:espn:'+team_id,'defense':'cfb:espn:'+defense_id,
                  'down':1,'yards_to_go':3,'yardline_100':3,'seconds_remaining':full_clock,
                  'score_diff':_integer(raw.get('start.pos_score_diff'),-100,100),'play_type':'extra_point',
                  'yards_gained':0,'elapsed_seconds':0,'drive_start':0,'complete_pass':0,
                  'interception':0,'fumble_lost':0,'field_goal_made':0,'punt_yards':0,
                  'turnover_return_yards':0,'passer_id':'','receiver_id':'','rusher_id':'',
                  'available_at':'','collected_at':'','source_version':'','reliability':'availability_unverified'}
        except ValueError:
            counts['invalid_identity_or_clock']+=1;continue
        # Conversion evidence is an actual published attempt, never inferred
        # from a six/seven-point score difference or a team average.
        conversion_base=dict(base)
        scoring_team=team_id
        if raw.get('defense_score_play') is True and raw.get('td_play') is True:
            scoring_team=defense_id
            conversion_base.update(offense='cfb:espn:'+defense_id,defense='cfb:espn:'+team_id,
                                   score_diff=-base['score_diff']+6)
        elif raw.get('offense_score_play') is True and raw.get('td_play') is True:
            conversion_base['score_diff']=base['score_diff']+6
        conversion=raw.get('two_point_conv_result')
        if conversion in ('success','failure'):
            output.append({**conversion_base,'play_id':base['play_id']+':conversion','play_type':'two_point','field_goal_made':int(conversion=='success')})
            played.append(event)
        elif scoring_team in (home_espn_id,away_espn_id) and raw.get('xp_attempt') is True and isinstance(raw.get('xp_made'),bool):
            output.append({**conversion_base,'play_id':base['play_id']+':conversion','field_goal_made':int(raw['xp_made'])})
            played.append(event)
        if not selected_team:continue
        if raw.get('penalty_no_play') or raw.get('penalty_negated_play') or raw.get('penalty_flag'):
            counts['penalty_coverage_excluded']+=1;continue
        try:period=_integer(raw.get('period'),1,20)
        except ValueError:
            counts['invalid_period']+=1;continue
        if period>4:
            counts['historical_overtime_excluded_from_regulation_pools']+=1;continue
        for flag in ('pass_attempt','rush','sack','int','pos_fumble_lost','punt','fg_attempt'):
            if raw.get(flag) is True:counts['source_'+flag]+=1
        try:
            down=_integer(raw.get('down'),1,4);distance=_integer(raw.get('distance'),1,100)
            field=_integer(raw.get('start.yardsToEndzone'),1,99)
            elapsed=_integer(full_clock-_integer(raw.get('end.adj_TimeSecsRem'),0,3600),0,90)
            qbid='cfb:espn:'+_id(raw['passer_player_id']) if raw.get('passer_player_id') is not None else ''
            receiver='cfb:espn:'+_id(raw['receiver_player_id']) if raw.get('receiver_player_id') is not None else ''
            runner='cfb:espn:'+_id(raw['rusher_player_id']) if raw.get('rusher_player_id') is not None else ''
            if raw.get('sack'):
                kind='sack';yards=_integer(raw.get('yds_sacked'),-99,0);complete=0
                if not qbid:raise ValueError('Sack identity missing')
                if yards==0:kind='rush';runner=qbid
            elif raw.get('pass_attempt'):
                kind='pass';complete=int(raw.get('completion') is True)
                if not qbid or complete and not receiver:raise ValueError('Passing identity missing')
                if raw.get('int'):
                    # Passing yards are zero on an interception. Its observed
                    # net turnover field change is retained separately below;
                    # missing air yards are not replaced by a guessed flight.
                    yards=0
                else:yards=_integer(raw.get('yds_receiving'),-99,99) if complete else 0
            elif raw.get('rush') or raw.get('kneel_down'):
                kind='kneel' if raw.get('kneel_down') else 'rush';yards=_integer(raw.get('yds_rushed'),-99,99);complete=0
                if not runner:raise ValueError('Rushing identity missing')
            elif raw.get('punt'):
                kind='punt';yards=0;complete=0
            elif raw.get('fg_attempt'):
                kind='field_goal';yards=0;complete=0
            else:
                counts['unsupported_play_type']+=1;continue
            interception=int(raw.get('int') is True);fumble=int(raw.get('pos_fumble_lost') is True)
            turnover_net=None
            if interception or fumble:
                if _id(raw.get('end.pos_team.id'))!=defense_id:raise ValueError('The turnover possession identity is not verified')
                turnover_net=100-field-_integer(raw.get('end.yard'),0,100)
            returned=_integer(raw.get('yds_punt_return'),0,100) if kind=='punt' and raw.get('yds_punt_return') is not None else 0
            punt=_integer(raw.get('yds_punted'),0,100) if kind=='punt' else 0
        except ValueError:
            counts['unsupported_event_or_participant_coverage']+=1;continue
        drive=(game_id,str(raw.get('drive.id')),team_id)
        start=drive not in seen_drives;seen_drives.add(drive)
        row={**base,'down':down,'yards_to_go':distance,'yardline_100':field,'play_type':kind,
             'yards_gained':yards,'elapsed_seconds':elapsed,'drive_start':int(start),
             'complete_pass':complete,'interception':interception,'fumble_lost':fumble,
             'field_goal_made':int(raw.get('fg_made') is True),'punt_yards':punt,
             'turnover_return_yards':returned,'passer_id':qbid,'receiver_id':receiver,'rusher_id':runner}
        if turnover_net is not None:row['turnover_net']=turnover_net
        if raw.get('EPA') is not None and math.isfinite(float(raw['EPA'])):row['epa']=raw['EPA']
        if isinstance(raw.get('EPA_success'),bool):row['success']=int(raw['EPA_success'])
        output.append(row);played.append(event);counts['accepted_plays']+=1
        for flag in ('pass_attempt','rush','sack','int','pos_fumble_lost','punt','fg_attempt'):
            if raw.get(flag) is True:counts['accepted_'+flag]+=1
        latest[team_id]=max(event,latest.get(team_id,event))
        for role,identifier,name_key in (('passer',qbid,'passer_player_name'),('receiver',receiver,'receiver_player_name'),('rusher',runner,'rusher_player_name')):
            if identifier and isinstance(raw.get(name_key),str) and raw[name_key].strip():
                item=catalog.setdefault(identifier,{'id':identifier,'name':raw[name_key].strip(),'team':'cfb:espn:'+team_id,'position':None,'observedRoles':[]})
                if role not in item['observedRoles']:item['observedRoles'].append(role)
        if counts['accepted_plays']>maximum_team_plays:
            raise ValueError('CFB team historical corpus exceeds its bounded play limit')
    del rows
    if not output or not played:raise ValueError('Insufficient identified CFB historical play evidence')
    fields=sorted(REQUIRED|{'sport','available_at','collected_at','source_version','reliability','epa','success','play_id','turnover_net'})
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(output)
    return {'csv':stream.getvalue(),'asOf':(max(played)+timedelta(microseconds=1)).isoformat(),
            'playerCatalog':list(catalog.values()),'counts':dict(counts),
            'latestTeamEvidenceAt':{team:value.isoformat() for team,value in latest.items()},
            'historicalGameIds':sorted({row['game_id'] for row in output if row['offense'] in ('cfb:espn:'+home_espn_id,'cfb:espn:'+away_espn_id)})}


def _prepare_cfb_public(data):
    global _prepared_cache
    if not isinstance(data,dict) or set(data)-{'game','simulations','seed'}:
        raise ValueError('Only a verified CFB game, complete-game count and seed may be requested')
    game=data.get('game')
    if not isinstance(game,dict) or not isinstance(game.get('home'),dict) or not isinstance(game.get('away'),dict):
        raise ValueError('A verified ESPN-identified CFB matchup is required')
    try:
        home=_id(game['home']['espnId']);away=_id(game['away']['espnId']);game_id=_id(game['espnGameId'])
    except (ValueError,KeyError) as exc:
        raise ValueError('Explicit ESPN CFB identifiers are required; CFBD and NFL IDs are not interchangeable') from exc
    if home==away:raise ValueError('Two distinct verified CFB teams are required')
    if game['home'].get('id')!='cfb:espn:'+home or game['away'].get('id')!='cfb:espn:'+away:
        raise ValueError('CFB source team IDs disagree with the canonical matchup')
    if game.get('id')!='cfb:espn:'+game_id:
        raise ValueError('The canonical CFB game ID disagrees with the source game ID')
    now=datetime.now(timezone.utc);event=utc(game.get('startTime'))
    if event<=now or game.get('status') in ('live','final','completed'):
        raise ValueError('A current pregame CFB analysis requires a future verified kickoff')
    season=game.get('season')
    if isinstance(season,bool) or not isinstance(season,int) or not 2014<=season<=now.year:
        raise ValueError('A supported verified CFB season is required')
    if event.year not in (season,season+1):
        raise ValueError('The CFB kickoff year is incompatible with its source season')
    count=data.get('simulations',10000)
    if not isinstance(count,int) or count not in (10000,50000,100000) or isinstance(count,bool):
        raise ValueError('Choose 10000, 50000 or 100000 complete CFB games')
    seed=data.get('seed',1)
    if isinstance(seed,bool) or not isinstance(seed,int) or abs(seed)>2**53:
        raise ValueError('An integer reproducible CFB seed is required')
    metadata=source_file(season)
    key=json.dumps([MODEL_VERSION,ENGINE_VERSION,game_id,home,away,season,game['startTime'],metadata['sha256']])
    if _prepared_cache and _prepared_cache['key']==key and time.monotonic()<_prepared_cache['until']:
        return _prepared_cache['value']
    cached=_prepared_games.get(key)
    if cached and time.monotonic()<cached['until']:
        _prepared_games.move_to_end(key)
        return cached['value']
    corpus=normalize_public_cfb(metadata['path'],home,away,now.isoformat())
    model=fit_cfb_csv(corpus['csv'],metadata['url']+'; publisher MIT repository; source availability unknown',corpus['asOf'],100,
                       {'recencyHalfLifeDays':90,'conditionalShrinkage':True})['model']
    if model['syntheticEvidence']:raise ValueError('Synthetic evidence cannot enter automatic CFB research')
    value={'game':game,'home':home,'away':away,'model':model,'corpus':corpus,'metadata':metadata}
    _prepared_cache={'key':key,'until':time.monotonic()+600,'value':value}
    _prepared_games[key]=_prepared_cache
    while len(_prepared_games)>4:_prepared_games.popitem(last=False)
    return value


def _research(prepared):
    metadata,corpus=prepared['metadata'],prepared['corpus']
    sources=[{'id':'cfb-public-pbp','name':'SportsDataverse ESPN-derived CFB play-by-play','url':metadata['url'],
              'collectedAt':metadata['collectedAt'],'availableAt':None,'version':metadata['sha256'],
              'status':'partial','note':'Public publisher source; current roster/availability and retrospective publication coverage are not complete.'},
             {'id':'cfb-source-license','name':'Publisher repository licence','url':SOURCE_LICENSE,'status':'available','collectedAt':metadata['collectedAt']}]
    return {'version':'automatic-cfb-research-8.0.0','sources':sources,
            'playerCatalog':corpus['playerCatalog'],'rejectedCounts':corpus['counts'],
            'latestTeamEvidenceAt':corpus['latestTeamEvidenceAt'],'historicalGameIds':corpus['historicalGameIds'],
            'injuryImpact':{'fullyAdjusted':False,'message':'Confirmed current CFB availability and calibrated injury impacts are unavailable.'},
            'dataAvailabilityVerified':False,'calibrationStatus':'Insufficient independent prospective CFB validation.'}


def prepare_cfb_public(data):
    prepared=_prepare_cfb_public(data);model=prepared['model']
    return {'sport':'CFB','ready':True,'inputHash':model['sha256'],'modelVersion':MODEL_VERSION,
            'engineVersion':ENGINE_VERSION,'rulesVersion':model['rulesVersion'],
            'training':{'plays':len(model['rows']),'games':len(prepared['corpus']['historicalGameIds'])},
            'research':_research(prepared),
            'limitations':['Ready means sufficient actual CFB empirical play coverage; it does not establish calibration, full availability adjustments or market value.']}


def analyze_cfb_public(data):
    prepared=_prepare_cfb_public(data)
    game,home,away,model,corpus=(prepared[key] for key in ('game','home','away','model','corpus'))
    count=data.get('simulations',10000)
    result=simulate_cfb(model,'cfb:espn:'+home,'cfb:espn:'+away,count,data.get('seed',1),game['startTime'],
                        parameter_uncertainty={'replicates':10,'gamesPerReplicate':100} if len(corpus['historicalGameIds'])>=8 else None,
                        representative_games=1)
    from .artifact_archive import archive_replay_input
    result=archive_replay_input(result,model,'CFB')
    result['limitations'].extend(['This automatically fitted baseline is conditional on historical player participation; current injury, depth-chart, transfer and snap-limit coverage is incomplete.',
                                  'Historical publication availability is unknown. Source retrieval today does not establish historical point-in-time availability or calibration.',
                                  'Penalties and unsupported source plays are excluded from the empirical corpus; see actual rejection counts.'])
    return {'status':'completed','sport':'CFB','game':game,'simulations':count,'modelVersion':MODEL_VERSION,
            'engineVersion':ENGINE_VERSION,'inputHash':model['sha256'],'result':result,
            'research':_research(prepared)}


def analyze_cfb_targets(data):
    """Exact statistical thresholds evaluated on shared complete NCAA games."""
    if not isinstance(data, dict) or set(data)-{'game','simulations','seed','contracts'}:
        raise ValueError('Trusted matchup and exact statistical targets required')
    definitions=data.get('contracts')
    if not isinstance(definitions,list) or not 2<=len(definitions)<=12:
        raise ValueError('Choose 2..12 distinct statistical targets')
    if any(not isinstance(d,dict) or d.get('kind') not in ('player','spread','total') for d in definitions):
        raise ValueError('Unsupported statistical target')
    base={k:v for k,v in data.items() if k!='contracts'}
    prepared=_prepare_cfb_public(base)
    model,game=prepared['model'],prepared['game']
    result=simulate_cfb(model,'cfb:espn:'+prepared['home'],'cfb:espn:'+prepared['away'],
        data.get('simulations',10000),data.get('seed',2026),game['startTime'],contracts=definitions)
    return {'sport':'CFB','inputHash':model['sha256'],'result':result,'research':_research(prepared)}
