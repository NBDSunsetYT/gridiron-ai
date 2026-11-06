"""Verify a completed research checkpoint without fitting or opening final tests.

Requires the preserved authorized artifact workspace. Public output contains
checksums, selected diagnostic IDs and receipts, never credentials or raw data.
"""
import sys,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import verify_parent
from modeling.dynamic_v24.completion.bank import HeadBank
from modeling.dynamic_v24.completion.data import LABELS
from modeling.overnight_v20.state import read,atomic,digest
from modeling.integration_v22.datasets import protected

def checkpoint():
    verify_parent();initial=read(OUT/'completion-r1/audit-start.json')
    for name,expected in initial['protectedFiles'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('Original checkpoint changed: '+name)
    import importlib.util
    spec=importlib.util.spec_from_file_location('specialized_report',ROOT/'scripts/report-specialized-v24.py');report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)
    result=read(ROOT/'docs/research/specialized-v24-results.json');bank=HeadBank(ROOT/'docs/research/specialized-v24-bank.json',ROOT)
    if bank.manifest['sha256']!=result['bankManifestSHA256']:raise ValueError('Report/bank version mismatch')
    loaded=[]
    for entry in bank.manifest['heads']:
        bank.load(entry)
        if entry['role']=='conditional_research_candidate' and (not entry.get('validationAvailableAfter') or entry['availableAfter'][:10]<entry['validationAvailableAfter']):raise ValueError('Candidate available before independent confirmation')
        loaded.append({'sport':entry['sport'],'stat':entry['stat'],'modelSHA256':entry['modelSHA256']})
    protocols=[];banned=protected()
    for folder,sport in report.PROTOCOLS:
        p=OUT/folder/'protocol.json';data=read(p);ids={g for w in data['selection'][sport] for g in w['games']}
        if ids&banned:raise ValueError('Protected game appears in new validation')
        protocols.append({'protocol':folder,'sport':sport,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'selection':data['selection'][sport],'numericCode':data['numericCode'],'sourceVersions':data['sourceVersions'],'excludedValidationCount':len(data.get('excludedValidationIds',[])),'excludedValidationSHA256':digest(data.get('excludedValidationIds',[]))})
    dest=ROOT/'docs/research';atomic(dest/'specialized-v24-protocols.json',{'evidenceTier':'conditional_corrected_history','protocols':protocols,'protectedOutcomesOpened':False,'rawDatasetsIncluded':False})
    replay=read(OUT/'completion-final/replay-verification.json');browser=read(OUT/'completion-final/browser.json');build=read(OUT/'completion-final/build-metrics.json')
    if not replay['allFrozenPointForecastsReplayed'] or not replay['allSelectedInputHashesEqual']:raise ValueError('Frozen numerical replay failed')
    if len(browser['checks'])!=6 or any(c['httpStatus']!=200 or c['errors'] or c['apiCalls'] or c['horizontalOverflow'] for c in browser['checks']):raise ValueError('Browser regression')
    python_log=(OUT/'completion-final/python-tests-final.log').read_text();frontend_log=(OUT/'completion-final/frontend-tests.log').read_text();type_log=(OUT/'completion-final/typecheck-final.log').read_text()
    if 'Ran 123 tests' not in python_log or not python_log.rstrip().endswith('OK'):raise ValueError('Final Python tests not passed')
    if '795 passed' not in frontend_log or '116 passed' not in frontend_log:raise ValueError('Frontend suite result missing')
    if 'error TS' in type_log:raise ValueError('TypeScript failed')
    receipt={'at':datetime.now(timezone.utc).isoformat(),'branch':'research/dynamic-v24','parentFilesVerified':len(read(OUT/'parent-integrity.json')),'originalAuditFilesVerified':len(initial['protectedFiles']),'modelArtifactsVerified':len(loaded),'distinctModelArtifactsVerified':len(bank.loaded),'modelBankSHA256':bank.manifest['sha256'],'protectedNewValidationIntersection':0,'sealedFinalOutcomesOpened':False,'pythonTestsPassed':123,'frontendTestsPassed':795,'frontendTestFilesPassed':116,'browserChecksPassed':6,'typeScriptPassed':True,'build':build,'browser':browser,'frozenForecastsReplayed':len(replay['checks']),'forecastRowsReplayed':sum(c['forecastRows'] for c in replay['checks']),'controlledJobs':result['resources'],'strictPregameForecasts':0,'productionPromotions':0,'productionDatabaseWrites':0,'migrationMerges':0,'noUnattendedExecutionClaim':True}
    receipt['activeAccounting']=read(OUT/'completion-final/active-accounting.json',{})
    atomic(dest/'specialized-v24-verification.json',receipt)
    paths=[p for directory in [ROOT/'modeling/dynamic_v24/completion',ROOT/'app/research/v24/models'] for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths.extend(ROOT/'scripts'/name for name in ['complete-models-v24.py','confirm-clean-nba-v24.py','efficient-nba-specialized-v24.py','extend-cfb-specialized-v24.py','extend-nfl-specialized-v24.py','nfl-game-heads-v24.py','nfl-scoring-heads-v24.py','replay-specialized-v24.py','report-specialized-v24.py','checkpoint-specialized-v24.py','check-specialized-ui-v24.mjs','verify-bank-pipeline-v24.py','verify-specialized-joint-v24.py'])
    paths.extend([ROOT/'modeling/test_specialized_v24.py',ROOT/'tests/specialized-research-page.test.ts',*sorted(dest.glob('specialized-v24*'))])
    paths=[p for p in paths if p.is_file()];atomic(OUT/'completion-final/checkpoint.json',{'at':receipt['at'],'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'resume':'python scripts/replay-specialized-v24.py && python scripts/report-specialized-v24.py && python scripts/checkpoint-specialized-v24.py','newNumericalExperimentsRequireNewProtocol':True})
    print(json.dumps({k:receipt[k] for k in ['parentFilesVerified','originalAuditFilesVerified','modelArtifactsVerified','pythonTestsPassed','frontendTestsPassed','browserChecksPassed','strictPregameForecasts','productionPromotions']}))
if __name__=='__main__':checkpoint()
