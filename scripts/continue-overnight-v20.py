"""Actual bounded supervisor; survives tool calls, not guaranteed VM shutdown.

Waits for an already-running controller to checkpoint, executes diagnostics and
one preregistered structural experiment, then drains the remaining frozen queue.
All numerical children use the same cumulative ledger and exclusive lease.
"""
import sys,os,time,json,subprocess,argparse,fcntl
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import read,atomic,now,process_identity,alive
from modeling.reconstruction_v19.runtime import local_only
local_only();OUT=ROOT/'artifacts/overnight-v20';p=argparse.ArgumentParser();p.add_argument('--slice-seconds',type=int,default=1800);args=p.parse_args()
if read(OUT/'runtime/accuracy-first-pause.json',{}).get('paused'):raise RuntimeError('Accuracy-first gate is paused. Complete the evidence/attribution audit before authorizing further bounded experiments; do not bypass missing evidence.')
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONHASHSEED='0');record=OUT/'runtime/supervisor.json';state=read(record,{'completedStages':[],'attempts':[]})
with (OUT/'runtime/supervisor.lock').open('a') as lease:
    try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise RuntimeError('The V20 supervisor is already active')
    state.update(status='active',identity=process_identity(os.getpid()),startedAt=now());atomic(record,state)
    # No competing experiment or duplicate controller is launched while the
    # previously verified real runner drains its in-flight workers.
    while any(s['status']=='active' and alive(s['identity']) for s in read(OUT/'runtime/state.json')['sessions']):
        state.update(stage='waiting_for_checkpoint',lastHeartbeatAt=now());atomic(record,state);time.sleep(5)
    stages=[('cfb-quarantine',['scripts/replay-overnight-v20.py','--sport','CFB','--event','cfb:espn:401643803','--variant','v19_reference','--quarantine']),('nfl-cold-replay',['scripts/replay-overnight-v20.py','--sport','NFL','--event','2024_06_ARI_GB','--variant','qb_mixture']),('nba-cold-replay',['scripts/replay-overnight-v20.py','--sport','NBA','--event','nba:espn:401703421','--variant','share_buzzer']),('hurdle',['scripts/research-hurdle-v20.py'])]
    for key,command in stages:
        if key in state['completedStages']:continue
        state.update(stage=key,lastHeartbeatAt=now());atomic(record,state)
        with (OUT/'logs'/('supervisor-'+key+'.log')).open('ab') as log:
            child=subprocess.Popen([sys.executable,*command],cwd=ROOT,env=env,stdout=log,stderr=log)
            while child.poll() is None:
                state.update(lastHeartbeatAt=now(),childIdentity=process_identity(child.pid));atomic(record,state);time.sleep(5)
        state['attempts'].append({'stage':key,'exitCode':child.returncode,'finishedAt':now()})
        if child.returncode==0:state['completedStages'].append(key)
        atomic(record,state)
    for attempt in range(20):
        s=read(OUT/'runtime/state.json');spec=read(OUT/'execution-spec-r1.json');keys=['r1-'+sport+'-'+str(c) for sport,c in spec['jobs']]
        if all(s['jobs'].get(k,{}).get('status') in ('completed','failed') for k in keys):break
        if s['measuredActiveSeconds']+s['unobservedActiveUpperBoundSeconds']+s.get('setupSafetyChargeSeconds',0)>35990:break
        state.update(stage='frozen_full_game_queue',lastHeartbeatAt=now());atomic(record,state)
        with (OUT/'logs'/'supervisor-full-game.log').open('ab') as log:
            child=subprocess.Popen([sys.executable,'scripts/research-overnight-v20.py','--resume','--revision','r1','--slice-seconds',str(args.slice_seconds)],cwd=ROOT,env=env,stdout=log,stderr=log)
            while child.poll() is None:
                state.update(lastHeartbeatAt=now(),childIdentity=process_identity(child.pid));atomic(record,state);time.sleep(5)
        state['attempts'].append({'stage':'frozen_full_game_queue','exitCode':child.returncode,'finishedAt':now()});atomic(record,state)
        if child.returncode!=0:break
        if read(OUT/'runtime/state.json').get('stopReason')!='execution_slice_checkpoint':break
    subprocess.run([sys.executable,'scripts/summarize-overnight-v20.py'],cwd=ROOT,env=env,check=False)
    state.update(status='checkpointed',stage='bounded_queue_finished_or_guarded',finishedAt=now(),lastHeartbeatAt=now());atomic(record,state);print(json.dumps(state,indent=2))
