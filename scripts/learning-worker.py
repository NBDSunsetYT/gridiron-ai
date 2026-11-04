"""One bounded LOCAL research job, safe for a workstation scheduler.

Never launched by page navigation. Completed experiments are read/verified, not
retrained; a changed source protocol fails closed inside the scientific runner.
No new held-out sample is silently selected after results have been exposed.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]


def state(folder):
    if (folder/'completed-report.json').exists():return 'complete'
    if (folder/'protocol.json').exists():return 'prepared'
    return 'no_frozen_protocol'


def reject_exposed_periods(folder,prior_protocols):
    """A new protocol cannot call an already opened final period untouched."""
    current=json.loads((folder/'protocol.json').read_text())
    periods=[r for r in current['coverage'] if r['phase']=='test']
    for old in prior_protocols:
        if old['sha256']==current['sha256']:continue # Exact replay/resume, not new evidence.
        for a in periods:
            for b in old['coverage']:
                if b['phase']=='test' and a['sport']==b['sport'] and a['start']<b['end'] and b['start']<a['end']:
                    raise RuntimeError('The '+a['sport']+' final period has already been exposed by another experiment. Reserve a new chronological period; no training was started.')


def run(folder):
    if os.environ.get('VERCEL') or os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID'):
        raise RuntimeError('Large research training is disabled on request-serving Vercel/Render hosts. Use a controlled local workstation.')
    status=state(folder)
    if status=='complete':
        spec=__import__('importlib.util',fromlist=['spec_from_file_location'])
        module_spec=spec.spec_from_file_location('verify_learning',ROOT/'scripts/verify-iterative-learning.py');module=spec.module_from_spec(module_spec);module_spec.loader.exec_module(module)
        report=module.verify(folder)
        print(json.dumps({'status':'already_complete','newSimulations':0,'verification':report}));return 0
    if status=='no_frozen_protocol':
        print(json.dumps({'status':status,'newSimulations':0,'message':'No eligible frozen experiment is queued; no compute was started.'}));return 0
    prior=[]
    for path in (ROOT/'artifacts').glob('learning-*/protocol.json'):
        if (path.parent/'final-selection-lock.json').exists():prior.append(json.loads(path.read_text()))
    published=ROOT/'docs/reports/v16-protocol.json'
    if published.exists() and (ROOT/'docs/reports/v16-iterative-learning.json').exists():prior.append(json.loads(published.read_text()))
    reject_exposed_periods(folder,prior)
    return subprocess.call([sys.executable,str(ROOT/'scripts/train-evaluate-engines.py'),'--run','--output',str(folder)],cwd=ROOT)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,default=ROOT/'artifacts/learning-v16');p.add_argument('--status',action='store_true');a=p.parse_args()
    if a.status:print(json.dumps({'status':state(a.folder)}))
    else:raise SystemExit(run(a.folder))
