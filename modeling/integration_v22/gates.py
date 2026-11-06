"""Keep V21's strict forecast gate and add model-bound consistency evidence."""
from ..evidence_v21.tiers import classify
from ..overnight_v20.state import digest
REQUIRED=('per_team_stat_reconciliation','regulation_clock_conservation','possession_counting','historical_play_count_realism','historical_possession_realism','ncaa_timing_regime','overtime_accounting')
def required_checks(sport):
    if sport not in ('NFL','CFB'):raise ValueError('Football consistency certificate requires NFL or CFB')
    return tuple('nfl_timing_regime' if k=='ncaa_timing_regime' and sport=='NFL' else k for k in REQUIRED)
def audit(model,match,evidence,certificate):
    failures=[]
    if model.get('sha256')!=digest({k:v for k,v in model.items() if k!='sha256'}):failures.append('model_content_checksum')
    if not certificate or certificate.get('modelHash')!=model.get('sha256'):failures.append('missing_or_wrong_model_consistency_certificate')
    else:
        if certificate.get('scope')!='historical_full_game_validation' or len(set(certificate.get('independentGames',[])))<12:failures.append('independent_full_game_validation_missing')
        for key in required_checks(model['sport']):
            if certificate.get('checks',{}).get(key) is not True:failures.append(key)
        body={k:v for k,v in certificate.items() if k!='sha256'}
        if certificate.get('sha256')!=digest(body):failures.append('consistency_certificate_checksum')
    q=classify(model['sport'],match['id'],match['cutoff'],evidence.get('components',{}),model_uncertainty=evidence.get('modelUncertainty'),consistency={k:False for k in failures} or {'consistency':True})
    q['newFullGameMatchupEligible']=q['fullGameSimulationAllowed'] is True;q['modelHash']=model['sha256'];q['reasons']=failures+q['missingDomains']+q['warnings'];return q
def require(model,match,evidence,certificate):
    q=audit(model,match,evidence,certificate)
    if not q['fullGameSimulationAllowed']:raise ValueError('Joint simulation withheld: '+', '.join(q['reasons']))
    return q
