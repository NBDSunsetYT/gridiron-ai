"""One bounded, preregistered forward confirmation; no Monte Carlo or tuning."""
import sys,os,time,json,gzip,pickle,threading,signal,resource,types,hashlib
from pathlib import Path
from collections import defaultdict
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20 import sources,data
from modeling.overnight_v20.cohort import training_rows,point_fit,point_predict,lineup,point_grade,official_box
from modeling.overnight_v20.state import Campaign,process_identity,read,atomic,digest
from modeling.accuracy_v20.projections import LeagueOpportunityModels
from modeling.accuracy_v20.benchmarks import OpponentAdjustedRolling
from modeling.accuracy_v20.quality import aware,assess
from modeling.accuracy_v20.evidence import quality_for
from modeling.accuracy_v20.outcomes import normalize_nba_final,VERSION as OUTCOME_VERSION
from modeling.accuracy_v20.membership import resolve_membership
from modeling.iterative_learning import freeze_json
from modeling.reconstruction_v19.runtime import local_only
local_only();OUT=ROOT/'artifacts/overnight-v20';F=OUT/'confirmation';spec=read(F/'protocol.json')
if not spec:raise RuntimeError('Freeze metadata-only confirmation protocol first')
if (F/'receipt.json').exists():print(json.dumps(read(F/'receipt.json'),indent=2));sys.exit(0)
for file,expected in spec['numericCode'].items():
    if hashlib.sha256((ROOT/file).read_bytes()).hexdigest()!=expected:raise RuntimeError('Locked numeric method changed; preserve the confirmation sample')
execution={'selectionSha256':digest(spec),'code':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'modeling/overnight_v20/sources.py',ROOT/'modeling/overnight_v20/cohort.py',ROOT/'modeling/accuracy_v20/evidence.py',ROOT/'modeling/accuracy_v20/quality.py',ROOT/'modeling/accuracy_v20/membership.py',ROOT/'modeling/accuracy_v20/outcomes.py']}}
if (F/'execution-spec.json').exists() and read(F/'execution-spec.json')!=execution:raise RuntimeError('Confirmation execution changed; preserve this registered run')
if not (F/'execution-spec.json').exists():freeze_json(F/'execution-spec.json',execution)
campaign=Campaign(OUT/'runtime');before=time.process_time();start=time.monotonic();stop=threading.Event()
def timeout(sig,frame):raise TimeoutError('Confirmation stopped by signal or declared wall budget')
signal.signal(signal.SIGTERM,timeout);signal.signal(signal.SIGINT,timeout);signal.signal(signal.SIGALRM,timeout)
with campaign.lease():
    campaign.begin();allowed,why=campaign.may_start(900)
    if not allowed:campaign.end(why);raise RuntimeError(why)
    campaign.claim('forward-confirmation-v20',process_identity(os.getpid()),900,spec);resource.setrlimit(resource.RLIMIT_CPU,(int(time.process_time())+900,int(time.process_time())+905));signal.alarm(1800)
    def heartbeat():
        while not stop.wait(5):campaign.heartbeat()
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start();receipt={'status':'interrupted','newSimulations':0,'productionWrites':0,'finalSetGraded':False};completed=[];pending=[]
    try:
        for sport in ['NFL','CFB','NBA']:
            games=spec['selection'][sport]
            if not games:continue
            folder=F/sport;folder.mkdir(exist_ok=True);packets=data.packets(sport);ep=folder/'evidence.json.gz'
            if ep.exists():evidence=json.loads(gzip.decompress(ep.read_bytes()))
            else:
                # Dependency injection scopes an existing read-only collector.
                # No global module, original protocol or evidence file is changed.
                original=sources.nba_evidence if sport=='NBA' else sources.nfl_evidence
                collector=types.FunctionType(original.__code__,{**original.__globals__,'protocol':lambda:{'selection':spec['selection']}})
                evidence=collector();freeze_json(ep,evidence)
            print(json.dumps({'stage':'confirmation_sources','sport':sport,'facts':len(evidence['facts'])}),flush=True)
            fp=folder/'forecasts.json.gz';cutoff=(min(aware(g['at']) for g in games)-timedelta(hours=6)).isoformat()
            if fp.exists():forecasts=json.loads(gzip.decompress(fp.read_bytes()))['rows']
            else:
                rows,ids=training_rows(packets,cutoff);base=point_fit(rows);predictions,_=point_predict(base,games,packets,evidence);heads=LeagueOpportunityModels(sport).fit(rows,cutoff);opps={};grouped=defaultdict(list)
                for r in rows:
                    if r['player']!='__team__':grouped[r['stat']].append(r)
                for stat,rs in grouped.items():
                    try:opps[stat]=OpponentAdjustedRolling().fit(rs)
                    except ValueError:pass
                history=defaultdict(list)
                for old in packets:
                    for team in [old['home'],old['away']]:history[team].append(old)
                extra={};quality=[];quality_map={};membership={}
                for g in games:
                    lf=lineup(g,evidence);features=[]
                    for team in [g['home'],g['away']]:features.extend(data.features_for(g,team,history,sport))
                    teams_by_player=defaultdict(set)
                    for r in features:
                        if r['player']!='__team__':teams_by_player[r['player']].add(r['team'])
                    facts=[{'sport':sport,'playerId':('nba:espn:'+f['playerId'] if sport=='NBA' and f['playerId'] else f['playerId']),'teamId':f['teamId'],'eventIds':[g['id']],'source':f['source'],'sourceVersion':f['sourceVersion'],'sourceVerified':f['confidence']=='official_timestamped_report','availableAt':f['publishedAt']} for f in evidence['facts'] if f['eventId']==g['id'] and f['playerId']]
                    for pid,teams in teams_by_player.items():
                        if len(teams)>1:membership[(g['id'],pid)]=resolve_membership(sport,g['id'],pid,teams,(aware(g['at'])-timedelta(minutes=30)).isoformat(),facts)
                        for team in teams:
                            q=quality_for(g,evidence['facts'],digest(spec['numericCode']),pid,team);quality_map[(g['id'],team,pid)]=q;quality.append(q)
                    by=defaultdict(list)
                    for r in features:
                        if r['player']!='__team__' and not r['player'].split(':')[-1].startswith('-'):by[r['stat']].append(r)
                    for stat,rs in by.items():
                        values={}
                        if stat in heads.models:values['opportunity_hurdle']=heads.predict(stat,rs)
                        if stat in opps:values['opponent_adjusted_rolling']=opps[stat].predict(rs)
                        for i,r in enumerate(rs):extra[(g['id'],r['team'],r['player'],stat)]={name:0. if r['player'] in lf[r['team']]['inactive'] else float(v[i]) for name,v in values.items()}
                    quality.append(quality_for(g,evidence['facts'],digest(spec['numericCode'])))
                forecasts=[];withheld=[]
                for r in predictions:
                    if r['player']=='__team__':continue
                    resolution=membership.get((r['gameId'],r['player']))
                    if resolution and (resolution['status']!='resolved' or resolution['teamId']!=r['team']):withheld.append({k:r[k] for k in ['gameId','team','player','stat']});continue
                    q=quality_map[(r['gameId'],r['team'],r['player'])];forecasts.append({**r,'predictions':{**r['predictions'],**extra.get((r['gameId'],r['team'],r['player'],r['stat']),{})},'unconditionalPublicationSuppressed':True,'researchDecision':q['decision'],'pointInTimeEvidenceScore':q['pointInTimeEvidenceScore'],'missingEvidence':q['missingDomains']})
                freeze_json(fp,{'rows':forecasts,'games':games,'fitCutoff':cutoff,'trainingGameIds':sorted(ids),'quality':quality,'withheldIdentityRows':withheld,'evidenceSha256':hashlib.sha256(ep.read_bytes()).hexdigest(),'methodLockedBeforeGrading':True,'newSimulations':0,'historicalReplay':True,'modelParameters':'Unchanged registered families and hyperparameters; ordinary earlier-data fitting only','finalSetGraded':False})
                with (folder/'models.pickle').open('xb') as f:pickle.dump({'base':base,'opportunityEfficiency':heads,'opponentRolling':opps},f)
            print(json.dumps({'stage':'confirmation_forecasts_frozen','sport':sport,'games':len(games),'rows':len(forecasts)}),flush=True)
            boxes={}
            for g in games:
                path=folder/'outcomes'/(g['id'].replace(':','_')+'.json.gz')
                if path.exists():boxes[g['id']]=json.loads(gzip.decompress(path.read_bytes()))['box'];continue
                try:
                    try:box=official_box(g,packets)
                    except StopIteration:
                        raw,source=sources.fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+g['id'].split(':')[-1])
                        if raw is None:raise ValueError('Final NBA response unavailable: HTTP '+str(source.get('httpStatus')))
                        box=normalize_nba_final(json.loads(raw),g['id'],g['home'],g['away'])
                    freeze_json(path,{'box':box,'forGradingOnly':True,'adapterVersion':OUTCOME_VERSION if sport=='NBA' else 'existing-football-final-box'});boxes[g['id']]=box
                except (ValueError,KeyError,TypeError) as e:pending.append({'sport':sport,'eventId':g['id'],'reason':str(e)})
            freeze_json(folder/'grades.json.gz',point_grade(forecasts,boxes,sport));completed.append({'sport':sport,'games':len(boxes),'rows':len(forecasts),'evidenceFacts':len(evidence['facts'])})
        receipt.update(status='completed',completed=completed,pending=pending,cpuSeconds=time.process_time()-before,wallSeconds=time.monotonic()-start,stopReason='single_locked_confirmation_completed_no_further_tuning')
        freeze_json(F/'receipt.json',receipt)
    finally:
        stop.set();thread.join(timeout=10);receipt.setdefault('cpuSeconds',time.process_time()-before);campaign.finish('forward-confirmation-v20',receipt);campaign.end(receipt.get('stopReason','confirmation_checkpoint'))
