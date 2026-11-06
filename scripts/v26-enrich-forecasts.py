"""A new pregame revision with recovered primary depth/college availability.

Do not overwrite revision 1 or pretend its backup-QB reference was a starter.
Backfill only an explicitly projected starter's earlier observed games; no
missing statistics, availability probabilities or simulation results invented.
"""
import sys,json,gzip,hashlib,io,csv,runpy,copy
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import numpy as np
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import digest
from modeling.evidence_v21.availability import Tables
from modeling.accuracy_v20.quality import aware
from modeling.integration_v22.datasets import protected
from modeling.accuracy_v25.opportunity_calendar import project


def main():
    old_path=ROOT/'artifacts/accuracy-v26/prospective-reference-r1.json';old_bytes=old_path.read_bytes();original=json.loads(old_bytes)
    if original['sha256']!=digest({k:v for k,v in original.items() if k!='sha256'}):raise ValueError('Original forecast changed')
    result=copy.deepcopy(original);result.pop('sha256');created=datetime.now(timezone.utc).isoformat()
    if any(aware(created)>=aware(g['eventAt']) for g in result['games']):raise ValueError('Do not backdate a new forecast after kickoff')
    f=runpy.run_path(str(ROOT/'scripts/v26-forecast.py'));capture=runpy.run_path(str(ROOT/'scripts/v26-capture.py'))
    manifest=json.load(open(ROOT/'artifacts/accuracy-v26/prospective-inputs-r1.json'));rosters={};histories={};raw={}
    for record in manifest['sources']:
        d=f['body'](record['receipt'])
        if record['kind']=='roster':rosters[(record['sport'],record['teamId'])]=f['roster_players'](d)
        else:histories[(record['sport'],record['eventId'])]=f['normalized'](d,record['sport']);raw[(record['sport'],record['eventId'])]=d
    depth={};depth_sources=[]
    for team,url in [('12','https://www.chiefs.com/team/depth-chart'),('20','https://www.newyorkjets.com/team/depth-chart'),('3','https://www.chicagobears.com/team/depth-chart'),('27','https://www.buccaneers.com/team/depth-chart')]:
        body,receipt=capture['get'](url);p=Tables();p.feed(body.decode(errors='replace'))
        qbs=[r[1:] for table in p.tables for r in table if r and r[0]=='QB']
        if len(qbs)!=1:raise ValueError('Primary QB depth order not uniquely supported')
        resolved=[]
        for rank,name in enumerate([name for name in qbs[0] if name],1):
            matches=[pid for pid,row in rosters[('NFL',team)].items() if f['norm'](row['name'])==f['norm'](name)]
            if len(matches)!=1:raise ValueError('Depth-chart player identity ambiguous: '+name)
            resolved.append({'playerId':matches[0],'name':name,'rank':rank})
        depth[team]=resolved;depth_sources.append({'teamId':team,'url':url,'sourceVersion':receipt['sourceVersion'],'capturedAt':receipt['retrievedAt'],'status':'projected_unofficial_depth_chart_not_confirmed_gameday_lineup'})
    college=json.load(open(ROOT/'artifacts/accuracy-v26/source-probes/cfb-current-rows.json'))
    # The extra earlier season is known and captured BEFORE the future event;
    # it is never used to pretend a reconstructed past source was pregame.
    url='https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2025.parquet'
    parquet,older_receipt=capture['get'](url)
    identity_path=ROOT/'artifacts/parallel-v19/sources/players.parquet';identity=pq.read_table(identity_path,columns=['espn_id','gsis_id','display_name']).to_pylist()
    banned=protected();schedule={r['game_id']:r for r in csv.DictReader((ROOT/'artifacts/parallel-v19/sources/nfl-games.csv').open())}
    older=pq.read_table(io.BytesIO(parquet),filters=[('game_id','not in',list(banned))]).to_pylist()
    changes=[];mapped_college=[];qb_stats={'passingAttempts':'attempts','passingCompletions':'completions','passingYards':'passing_yards','passingTouchdowns':'passing_tds','interceptions':'passing_interceptions'}
    for g in result['games']:
        old_hash=g.pop('predictionHash');g['previousPredictionHash']=old_hash;g['forecastCapturedAt']=created
        g['primaryDepthChartSources']=[s for s in depth_sources if any(t['teamId']==s['teamId'] for t in g['teams'])] if g['sport']=='NFL' else []
        for p in g['players']:
            if g['sport']=='NFL' and any(stat in (p.get('reference') or {}) for stat in ('passingAttempts','passingYards')):
                entry=next((r for r in depth[p['teamId']] if r['playerId']==p['playerId']),None)
                p['projectedQBDepthRank']=entry['rank'] if entry else None
                p['starterStatus']='projected_primary' if entry and entry['rank']==1 else 'backup_or_unresolved_not_primary_forecast'
                if not entry or entry['rank']!=1:changes.append({'sport':'NFL','eventId':g['eventId'],'player':p['name'],'change':'Backup reference retained, not presented as projected starting QB'})
            if g['sport']=='CFB':
                facts=[c for c in college if c['teamId']==p['teamId'] and f['norm'](c['name'])==f['norm'](p['name'])]
                if facts:
                    fact=facts[-1];p['availability']=fact['status'].lower();p['availabilityEvidence']={k:fact[k] for k in ('source','embeddedSource','sourceVersion','capturedAt','phase')}
                    mapped_college.append({'playerId':p['playerId'],'name':p['name'],'status':fact['status'],'teamId':p['teamId']})
                    if p['availability'] in ('out','doubtful'):
                        p['reference']=None;p['withheld']='Primary SEC status is '+fact['status']+'; no active-role estimate';changes.append({'sport':'CFB','eventId':g['eventId'],'player':p['name'],'change':'Withheld using newly recovered primary report'})
        if g['sport']=='NFL':
            for team in g['teams']:
                first=depth[team['teamId']][0];pid=first['playerId'];p=next((p for p in g['players'] if p['playerId']==pid),None)
                if p is not None and p.get('reference',{}).get('passingAttempts',{}).get('observations',0)>=5:continue
                refs=[]
                for gid in g['inputGameIds'][team['teamId']]:
                    record=histories[('NFL',gid)]['teams'][team['teamId']]['players'].get(pid)
                    if record and record['stats'].get('passingAttempts',0)>0:refs.append({'gameId':gid,'at':histories[('NFL',gid)]['at'],'stats':record['stats']})
                ids=[r['gsis_id'] for r in identity if str(r['espn_id'])==pid and f['norm'](r['display_name'])==f['norm'](first['name'])]
                if len(set(ids))!=1:continue
                for record in older:
                    if record['player_id']!=ids[0] or not record.get('attempts') or record['game_id'] not in schedule:continue
                    s=schedule[record['game_id']];at=datetime.fromisoformat(s['gameday']+'T'+s['gametime']).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc).isoformat()
                    if aware(at)>=aware(created):raise ValueError('Future backfill row')
                    refs.append({'gameId':record['game_id'],'at':at,'stats':{k:float(record[v]) for k,v in qb_stats.items() if record.get(v) is not None}})
                refs=sorted(refs,key=lambda r:r['at'])[-5:]
                if len(refs)<3:continue
                estimates={}
                for stat in qb_stats:
                    values=[r['stats'][stat] for r in refs if stat in r['stats']]
                    if len(values)<3:continue
                    estimates[stat]={'mean':float(np.mean(values)),'median':float(np.median(values)),'observations':len(values),'historicalRange':[min(values),max(values)],'predictionInterval90':None,'intervalReason':'Conditional rolling reference, no validated coverage','sourceGameIds':[r['gameId'] for r in refs if stat in r['stats']]}
                if p is None:
                    p={'playerId':pid,'teamId':team['teamId'],'name':first['name'],'position':'QB','availability':'unknown_not_assumed_healthy','approvedRoute':None,'independentlyValidated':False};g['players'].append(p)
                p.update(reference=estimates,projectedQBDepthRank=1,starterStatus='projected_primary',conditionalOn='Projected QB starter participates; primary depth is unofficial and restrictions unverified',priorSeasonBackfill=True)
                changes.append({'sport':'NFL','eventId':g['eventId'],'player':p['name'],'change':'Projected starting QB reference supported by earlier season plus current observations','sourceGameIds':[r['gameId'] for r in refs]})
        for p in g['players']:
            if not p.get('reference'):continue
            team_history=[histories[(g['sport'],i)] for i in g['inputGameIds'][p['teamId']]];owned={r['eventId']:raw[(g['sport'],r['eventId'])] for r in team_history}
            p['calendarExposureCandidate']={}
            for stat in p['reference']:
                candidate=project(team_history,owned,g['sport'],p['teamId'],p['playerId'],stat)
                if candidate:p['calendarExposureCandidate'][stat]=candidate
        g['predictionHash']=digest(g)
    result.update(version='source_enriched_prospective_references-26.1',createdAt=created,previousSnapshotHash=original['sha256'],
                  methodCodeSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),changes=changes,
                  primaryCollegeFacts=college,primaryCollegeMappedPlayers=mapped_college,
                  primaryNFLDepthCharts=depth_sources,priorSeasonBackfillSource={'url':url,'sourceVersion':older_receipt['sourceVersion'],'capturedAt':older_receipt['retrievedAt'],'protectedRowsExcluded':True,'identityMapSHA256':hashlib.sha256(identity_path.read_bytes()).hexdigest()})
    result['sha256']=digest(result);freeze_json(ROOT/'artifacts/accuracy-v26/prospective-reference-r2.json',result);freeze_json(ROOT/'docs/research/V26_PROSPECTIVE_R2.json.gz',result)
    if old_path.read_bytes()!=old_bytes:raise ValueError('Original predictions were modified')
    print(json.dumps({'capturedAt':created,'changes':changes,'mappedCollegePlayers':len(mapped_college),'originalForecastPreserved':True,'strictJointForecasts':0}),flush=True)


if __name__=='__main__':main()
