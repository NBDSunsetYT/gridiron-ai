"""Official box-score reconciliation for GRADING ONLY.
Never import into pregame features. Missing categories are unavailable, not zero.
A verified complete counting-stat category permits a zero for an unlisted player;
this says nothing about injury status or whether that player participated.
"""
import math
from collections import defaultdict

def number(v):
    try:
        n=float(str(v).replace(',',''))
        return n if math.isfinite(n) else None
    except (ValueError,TypeError):return None

def normalize_box(payload,sport,event_id,expected_home,expected_away,id_map=None):
    header=payload['header'];competition=header['competitions'][0]
    if header['id']!=str(event_id).split(':')[-1] and sport=='CFB':raise ValueError('CFB event identifier mismatch')
    if not competition['status']['type'].get('completed'):raise ValueError('Official outcome is not final')
    competitors={c['homeAway']:c for c in competition['competitors']};team_ids={str(competitors['home']['team']['id']):expected_home,str(competitors['away']['team']['id']):expected_away}
    if sport=='CFB' and (expected_home!='cfb:espn:'+str(competitors['home']['team']['id']) or expected_away!='cfb:espn:'+str(competitors['away']['team']['id'])):raise ValueError('CFB team mapping mismatch')
    if sport=='NFL':
        aliases={'LAR':'LA','WSH':'WAS'}
        for side,expected in [('home',expected_home),('away',expected_away)]:
            actual=competitors[side]['team']['abbreviation']
            if aliases.get(actual,actual)!=expected:raise ValueError('NFL team identity mismatch')
    players={};coverage={};unmapped=[];team_aggregates={};team_credited=[]
    for t in payload['boxscore']['players']:
        if str(t['team']['id']) not in team_ids:raise ValueError('Box-score team identity mismatch')
        team=team_ids[str(t['team']['id'])];available=set();aggregate=defaultdict(float)
        for category in t['statistics']:
            name=category['name'];labels=category.get('labels',[])
            if name not in ('passing','rushing','receiving'):continue
            if name=='passing':fields={'YDS':'passingYards','TD':'passingTouchdowns','INT':'interceptions'}
            elif name=='rushing':fields={'CAR':'carries','YDS':'rushingYards','TD':'rushingTouchdowns'}
            else:fields={'REC':'receptions','YDS':'receivingYards','TD':'receivingTouchdowns','TGTS':'targets','TGT':'targets'}
            available.update(stat for label,stat in fields.items() if label in labels)
            if name=='passing' and 'C/ATT' in labels:available.update(('passingAttempts','completions'))
            for row in category.get('athletes',[]):
                athlete=row['athlete'];provider_id=str(athlete['id']);values=dict(zip(labels,row['stats']));stats={}
                for label,stat in fields.items():
                    if label in values:
                        value=number(values[label])
                        if value is None:raise ValueError('Nonnumeric official counting statistic')
                        stats[stat]=value
                if name=='passing' and 'C/ATT' in values:
                    a=values['C/ATT'].split('/')
                    if len(a)!=2 or any(number(x) is None for x in a):raise ValueError('Malformed completions/attempts')
                    stats.update(completions=number(a[0]),passingAttempts=number(a[1]))
                for stat,value in stats.items():aggregate[stat]+=value
                if provider_id.startswith('-') or athlete.get('displayName','').strip().lower()=='team':team_credited.append({'team':team,'statistics':stats});continue
                pid='cfb:espn:'+provider_id if sport=='CFB' else (id_map or {}).get(provider_id)
                if not pid:unmapped.append({'team':team,'providerId':provider_id,'name':athlete.get('displayName'),'stats':stats});continue
                p=players.setdefault(pid,{'team':team,'stats':{},'name':athlete.get('displayName')})
                if p['team']!=team:raise ValueError('One player mapped to both teams')
                for stat,value in stats.items():
                    if stat in p['stats']:raise ValueError('Duplicate category/stat mapping')
                    p['stats'][stat]=value
        coverage[team]=sorted(available);team_aggregates[team]=dict(aggregate)
    checks=[]
    for team,t in team_aggregates.items():
        for left,right in [('passingYards','receivingYards'),('completions','receptions'),('passingTouchdowns','receivingTouchdowns')]:
            if left in t and right in t:checks.append({'team':team,'left':left,'right':right,'equal':abs(t[left]-t[right])<1e-9,'difference':t[left]-t[right]})
    # Category-level completeness is withheld when nonzero athletes cannot map.
    for row in unmapped:
        for stat,v in row['stats'].items():
            if v and stat in coverage[row['team']]:coverage[row['team']].remove(stat)
    return {'eventId':event_id,'sport':sport,'scheduledStart':competition['date'],'scores':{expected_home:float(competitors['home']['score']),expected_away:float(competitors['away']['score'])},'players':players,'supportedStatisticsByTeam':coverage,'teamStatTotals':team_aggregates,'teamCreditedStatistics':team_credited,'unmapped':unmapped,'accountingChecks':checks,'outcomesVerified':True,'notForPregameFeatures':True}

def player_outcome(box,pid,team,stat):
    if stat not in box['supportedStatisticsByTeam'].get(team,[]):return None,'official_category_unavailable_or_identity_incomplete'
    row=box['players'].get(pid)
    if row and row['team']!=team:return None,'player_team_mismatch'
    return (row['stats'].get(stat,0.) if row else 0.),'official_counting_stat_zero_is_not_DNP_or_injury'
