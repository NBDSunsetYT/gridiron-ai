"""Audit existing source clocks and censored-law support, without refitting.

These are previously exposed mechanics cases, not new accuracy evidence.
Administrative charges are not replaced by zero or ordinary live-play priors.
"""
import sys,json,pickle,hashlib,time
from pathlib import Path
from collections import defaultdict
import numpy as np
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.fullgame_v23.replay import ordered_rows,clock_seconds,clock_audit
from modeling.integration_v22.clock import RuntimeClock,serialize_clock
from modeling.integration_v22.datasets import protected
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import digest
from modeling.fullgame_v23.rules import cfb_period_extension
from modeling.overnight_v20.data import archives
OUT=ROOT/'artifacts/forecast-certification-v28/cfb-clock-r2'

def run():
    start=time.monotonic();cpu=time.process_time();folder=ROOT/'artifacts/evidence-and-joint-v27';selection=json.loads((folder/'selection-clock-eligible.json').read_text())['selection']['CFB'];ids=[g for g in selection if g not in protected()];path=Path('/tmp/gridiron-cfb-public-pbp-2024.parquet');artifact=ROOT/'artifacts/overnight-v21/clock/censored_drive_em2.pickle';law=serialize_clock(pickle.load(artifact.open('rb')));sourcehash=hashlib.sha256(path.read_bytes()).hexdigest();rows=defaultdict(list);metadata=archives('CFB')['games']
    columns=['game_id','id','period','clock.displayValue','sequenceNumber','sequence_number','text','penalty_flag','penalty_no_play','type.text','drive.id']
    columns=[c for c in columns if c in pq.read_schema(path).names]
    for r in pq.read_table(path,columns=columns,filters=[('game_id','in',[int(g.split(':')[-1]) for g in ids])]).to_pylist():rows['cfb:espn:'+str(int(r['game_id']))].append(r)
    protocol={'cohort':ids,'scope':'Previously exposed source-clock mechanics, not forecast accuracy','fitCutoff':law['metadata']['fitCutoff'],'modelSHA256':digest(law),'sourceSHA256':sourcehash,'seed':280028,'refit':False,'eventTimePolicy':'Actual owned source event time per game, not a uniform diagnostic date','revisionReason':'Bind RuntimeClock to each real source event time; preserve R1 mechanical probe without claiming historical temporal eligibility','fullGamesSimulated':0,'protectedExcluded':True,'codeSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};freeze_json(OUT/'protocol.json',protocol);cases=[];rng=np.random.default_rng(280028)
    for gid,rs in rows.items():
        ordered=ordered_rows(rs,'CFB');same=0;backward=0
        for a,b in zip(ordered,ordered[1:]):
            if a['period']!=b['period'] or a['period']>4:continue
            gap=clock_seconds(a['clock.displayValue'])-clock_seconds(b['clock.displayValue']);same+=gap==0;backward+=gap<0
        event_at=metadata[gid]['firstObservedAt'];draws=[];timing_eligible=True
        try:
            runtime=RuntimeClock(law,event_at)
            for kind in law['supported']:
                if kind=='penalty':continue
                for complete in (False,True):
                    for hurry in (False,True):draws.extend(np.searchsorted(runtime.cdf(kind,complete,hurry),rng.random(64)).tolist())
            try:runtime.cdf('penalty',False,False);admin='supported'
            except ValueError as e:admin=str(e)
        except ValueError as e:timing_eligible=False;admin=str(e)
        case={'gameId':gid,'sourceEventAt':event_at,'clockFitPrecedesEvent':timing_eligible,'sourceRows':len(rs),'sameClockAnchorsCensored':same,'backwardAnchors':backward,'clockAudit':clock_audit(rs,'CFB'),'positiveLatentSamples':len(draws),'zeroLatentSamples':sum(v<=0 for v in draws),'administrativeTiming':admin,'fullGameTimingCertified':False};cases.append(case)
    extension=[{'season':y,'period':q,'reason':r,**cfb_period_extension(y,q,r)} for y in (2023,2024) for q in (1,2,3,4) for r in ('accepted_live_ball_foul','offsetting_fouls','inadvertent_whistle')]
    report={'protocol':protocol,'gamesAudited':len(cases),'cases':cases,'sameClockAnchorsCensored':sum(c['sameClockAnchorsCensored'] for c in cases),'positiveLatentSamples':sum(c['positiveLatentSamples'] for c in cases),'zeroLatentSamples':sum(c['zeroLatentSamples'] for c in cases),'extensionCases':extension,'strictForecasts':0,'clockGateReleased':False,'blockers':['Unresolved administrative/runoff elections and live-ball penalty sequence law','Season-specific full rulebook exceptions and independently reconciled possession/pace distributions','Historical pregame availability and edition evidence'],'cpuSeconds':time.process_time()-cpu,'wallSeconds':time.monotonic()-start};freeze_json(OUT/'results.json',report);print(json.dumps({k:report[k] for k in ('gamesAudited','sameClockAnchorsCensored','positiveLatentSamples','zeroLatentSamples','clockGateReleased','cpuSeconds')}))

if __name__=='__main__':run()
