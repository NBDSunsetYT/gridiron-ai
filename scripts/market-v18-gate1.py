"""Run required commands or seal Gate 1 after the frozen 500-game audit.

Run --tests first. The default invocation refuses incomplete audit results.
No training, production calls, market-price substitution, or model tuning.
"""
import sys, re, json, time, subprocess, hashlib, resource
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import read, atomic
from modeling.market_gates_v18 import gate1
from modeling.market_audit_report_v18 import audit_report,matched_coverage
OUT=ROOT/'artifacts/market-v18'

def tests():
    receipts=[]
    for command, name in [(['npm','test'],'ts'), (['npm','run','test:python'],'python'), (['npm','run','typecheck'],'typecheck')]:
        path=OUT/('gate1-final-'+name+'.log');start=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
        with path.open('w') as stream:
            completed=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=600)
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt={'command':command,'exitCode':completed.returncode,'wallSeconds':time.monotonic()-start,
                 'cpuSeconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                 'logSHA256':hashlib.sha256(path.read_bytes()).hexdigest()}
        receipts.append(receipt);atomic(OUT/'gate1-final-test-receipts.json',receipts)
        print(json.dumps(receipt),flush=True)
        if completed.returncode:raise RuntimeError('Required test command failed')
    ts=(OUT/'gate1-final-ts.log').read_text();py=(OUT/'gate1-final-python.log').read_text()
    counts={'tsPassed':int(re.search(r'Tests\s+(\d+) passed',ts)[1]),
            'pythonPassed':int(re.search(r'Ran (\d+) tests',py)[1]),
            'typecheckPassed':True,'allCommandsExitZero':all(r['exitCode']==0 for r in receipts)}
    atomic(OUT/'gate1-tests.json',counts)

def seal():
    protocol=read(OUT/'r5/audit-protocol.json');rows=[read(p) for p in (OUT/'r5/runs').glob('*.summary.json')]
    report=audit_report(rows,[r['gameId'] for r in protocol['selection']]);checks=read(OUT/'gate1-tests.json') or {}
    import importlib.util
    spec=importlib.util.spec_from_file_location('market_audit_grade_reader',ROOT/'scripts/market-v18-audit.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    report['originalObservationCoverage']=matched_coverage(rows,{r['gameId']:reader.actual(r).get('playerErrors',[]) for r in protocol['selection']})
    report['playerMetricScope']='Matched original observations only; omitted roster/stat predictions are reported, never replaced with zero'
    audit={'gamesCompleted':len(rows),'simulatedCompleteGames':sum(r['simulations'] for r in rows),
           'allAccountingReconciled':all(r['accountingReconciled'] for r in rows)}
    decision=gate1(checks,audit)
    decision.update(tests=checks,audit=audit,protocolSHA256=hashlib.sha256((OUT/'r5/audit-protocol.json').read_bytes()).hexdigest(),
                    baselineCoefficientsRefit=False,productionWrites=0)
    atomic(OUT/'stage1-regression-report.json',report);atomic(OUT/'gate1.json',decision)
    print(json.dumps(decision))
    if not decision['passed']:raise RuntimeError('Gate 1 remains closed')

if __name__=='__main__':
    if '--tests' in sys.argv:tests()
    else:seal()
