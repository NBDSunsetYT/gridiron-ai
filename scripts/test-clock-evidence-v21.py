"""Conditional timing-component validation. Never fits or reads score targets."""
import sys,json,gzip,pickle,random,hashlib
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.clock_data import blocks_from_rows,official_drive_rows,official_sequences,verify_book,official_team_codes,clock_accounting
from modeling.evidence_v21.clock import CensoredClock
from modeling.evidence_v21.runtime import job
from modeling.evidence_v21.io import OUT
from modeling.overnight_v20.state import read,atomic
from modeling.overnight_v20.data import archives
from modeling.iterative_learning import freeze_json
from modeling.structural_v18.models import error_metrics,cluster_delta
from pypdf import PdfReader
import pyarrow.parquet as pq

def run():
 p=read(OUT/'protocol-final.json');a=archives('CFB');clock_ids={g['id'] for g in p['selection']['CFB']};eligible={gid:g for gid,g in a['games'].items() if g['firstObservedAt'][:10]<'2024-10-01' and gid not in {x['id'] for gs in p['sealedFinal'].values() for x in gs}};cs=['game_id','id','sequenceNumber','clock.displayValue','drive.id','drive.timeElapsed.displayValue','drive.start.clock.displayValue','drive.end.clock.displayValue','drive.start.period.number','drive.end.period.number','type.text','text','start.team.id','pos_team_id','homeTeamAbbrev','awayTeamAbbrev','period.number','sack','rush','pass_attempt','completion','start.down','start.yardsToEndzone'];rs=pq.read_table('/tmp/gridiron-cfb-public-pbp-2024.parquet',columns=cs).to_pylist();blocks,rejected=blocks_from_rows(rs,eligible);train=[b for b in blocks if b['eventEnd'][:10]<'2024-09-20'];random.Random(21021).shuffle(train);train=train[:600];val=[b for b in blocks if b['eventId'] in clock_ids];models={};rows=[];baseline=defaultdict(list)
 for r in a['rows']:
  if r['at'][:10]<'2024-09-20' and r.get('elapsed') is not None and 0<=r['elapsed']<=90:baseline[r['kind']].append(r['elapsed'])
 folder=OUT/'clock';folder.mkdir(exist_ok=True)
 for name,iterations in [('positive_inter_event_prior',0),('censored_drive_em2',2)]:
  path=folder/(name+'.pickle');pred=folder/(name+'-predictions.json.gz')
  if path.exists() and pred.exists():
   model=pickle.loads(path.read_bytes());rr=json.loads(gzip.decompress(pred.read_bytes()))
  else:
   model=CensoredClock().fit(train,'2024-09-20T00:00:00Z',iterations);rr=[]
   for b in val:
    before=sum(np.mean(baseline[x['kind']]) for x in b['plays']);rr.append({'gameId':b['eventId'],'blockId':b['id'],'actual':b['elapsedSeconds'],'baseline':float(before),'prediction':model.forecast_seconds(b['plays']),'candidate':name,'observedActionSequenceConditioned':True})
   freeze_json(pred,rr)
   with path.open('xb') as f:pickle.dump(model,f)
  models[name]=model;rows.extend(rr)
  print(json.dumps({'stage':'clock_model_fitted','candidate':name,'trainingBlocks':len(train),'validationBlocks':len(val)}),flush=True)
 book_validation=[];representatives=[]
 for rec in read(OUT/'gamebooks/manifest.json',[]):
  gid=rec['eventId'];g=a['games'][gid];pages=[page.extract_text(extraction_mode='layout') for page in PdfReader(ROOT/rec['path']).pages];own=[b for b in blocks if b['eventId']==gid];raw=next(r for r in rs if 'cfb:espn:'+str(int(r['game_id']))==gid);aliases={__import__('re').sub('[^a-z0-9]','',g[side+'Name'].lower()):raw[side+'TeamAbbrev'] for side in ['home','away']}
  # Explicit official spelling abbreviation, not fuzzy cross-game identity.
  if 'ballstate' in aliases:aliases['ballst']=aliases['ballstate']
  chart='\n'.join(t for t in pages if 'Drive Chart' in t);codes=official_team_codes(chart,aliases);dr=official_drive_rows(chart,aliases);seq=official_sequences(pages,aliases,codes);matched,unmatched=verify_book(own,dr,rec,seq);reconstructed=[]
  for b in matched:
   if not b['sequenceVerified']:continue
   try:
    r=models['censored_drive_em2'].reconstruct(b,21021,samples=16);reconstructed.append(r)
    if len(representatives)<4:representatives.append(r)
   except ValueError as e:unmatched.append({'blockId':b['id'],'reason':str(e)})
  book_validation.append({'eventId':gid,'source':rec,'teamCodeEvidence':codes,'clockAccounting':clock_accounting(pages,dr,codes),'independentDriveRows':len(dr),'providerSupportedBlocks':len(own),'matchingClockAnchors':len(matched),'independentlyMatchedPlaySequences':sum(b['sequenceVerified'] for b in matched),'reconstructedBlocks':len(reconstructed),'reconstructedTimedPlays':sum(len(r['meanSeconds']) for r in reconstructed),'sumConservationMaximumError':max((abs(sum(r['meanSeconds'])-r['totalSeconds']) for r in reconstructed),default=None),'recordedZeroIntervalsInsideReconstructedBlocks':sum(sum(d==0 for d in b['providerRecordedIntervals']) for b in matched if b['sequenceVerified']),'fieldOrSequenceConflicts':[{'id':b['id'],'reason':b['sequenceReason']} for b in matched if not b['sequenceVerified']],'unmatched':unmatched,'fullGameClockGateResolved':False,'remaining':'Administrative runoff, missing sequences, field-location conflicts and timing-regime state remain explicitly unresolved.'})
  print(json.dumps({'stage':'independent_gamebook','eventId':gid,'reconstructedBlocks':len(reconstructed)}),flush=True)
 result={'version':'clock-component-21.0.0','tier':'conditional_component_diagnostic','fitCutoff':'2024-09-20T00:00:00Z','scoreTargetsRead':False,'newCompleteGameSimulations':0,'validationGames':len({b['eventId'] for b in val}),'validationBlocks':len(val),'rejectedSourceBlocks':dict(Counter(r['reason'] for r in rejected)),'trainingGames':len({b['eventId'] for b in train}),'models':{},'independentGamebooks':book_validation,'interpretation':'Unseen drive elapsed-time forecasts are conditioned on observed play types, not pregame game forecasts. Anchor-conditioned reconstructions are measurement repairs and cannot be counted as predictive accuracy wins.'}
 for name,model in models.items():
  rr=[r for r in rows if r['candidate']==name];result['models'][name]={'metadata':model.metadata,'errors':error_metrics([r['actual'] for r in rr],[r['prediction'] for r in rr]),'baseline':error_metrics([r['actual'] for r in rr],[r['baseline'] for r in rr]),'pairedDelta':cluster_delta([dict(r,y=r['actual'],player='drive') for r in rr],[r['baseline'] for r in rr],[r['prediction'] for r in rr],21021)}
 reports=OUT/'clock/reports'/REPORT_REVISION;reports.mkdir(parents=True,exist_ok=True);freeze_json(reports/'drive-predictions.json.gz',rows);freeze_json(reports/'representative-latent-intervals.json.gz',representatives);atomic(reports/'results.json',result)
 return {'clockComponentValidationGames':result['validationGames'],'clockComponentValidationBlocks':len(val),'independentlyReconstructedBlocks':sum(v['reconstructedBlocks'] for v in book_validation),'fullGameGateResolved':False,'newCompleteGameSimulations':0}
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--revision',default='r1');args=parser.parse_args();REPORT_REVISION=args.revision;print(json.dumps(job('clock-components',run,cpu=1200,wall=1800,revision=args.revision),indent=2))
