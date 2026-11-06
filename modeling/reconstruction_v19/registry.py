"""Six independent, append-only champion slots. No production writes by research.
CAS and a process lock prevent two optimizers silently replacing a champion.
Rollback is a new event; prior forecasts/model versions are never rewritten.
"""
from pathlib import Path
import json,os,fcntl,hashlib
from contextlib import contextmanager
from .evidence import canonical
SLOTS=tuple(s+':'+p for s in ('NFL','CFB','NBA') for p in ('player','moneyline'))

def promotion_reasons(result,gate):
    reasons=[]
    if result.get('games',0)<gate['minGames']:reasons.append('insufficient_independent_games')
    if result.get('windows',0)<gate['minWindows']:reasons.append('insufficient_chronological_windows')
    if result.get('pointInTimeAvailabilityCoverage',0)<gate['minVerifiedAvailabilityCoverage']:reasons.append('pregame_availability_coverage')
    if not result.get('outcomesVerified'):reasons.append('unverified_outcomes')
    if result.get('dataQualityFailures'):reasons.append('critical_data_quality_failure')
    if result.get('tunedOnFinalTest'):reasons.append('final_test_contamination')
    if not result.get('primaryDeltaCI') or result['primaryDeltaCI'][1]>=0:reasons.append('primary_improvement_not_credible')
    if result.get('moneylineBrierDelta',float('inf'))>gate['maxBrierRegression']:reasons.append('moneyline_brier_regression')
    if result.get('moneylineLogLossDelta',float('inf'))>gate['maxLogLossRegression']:reasons.append('moneyline_log_loss_regression')
    if result.get('importantCategoryMaxRegression',float('inf'))>gate['maxImportantCategoryRegression']:reasons.append('important_player_category_regression')
    if not result.get('allWindowsNonRegressing'):reasons.append('cross_window_instability')
    return reasons

class Registry:
    def __init__(self,path):self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
    @contextmanager
    def locked(self):
        with (self.path/'registry.lock').open('a') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            try:yield
            finally:fcntl.flock(f,fcntl.LOCK_UN)
    def events(self):
        result=[]
        for p in sorted(self.path.glob('*.json')):
            row=json.loads(p.read_text());body={k:v for k,v in row.items() if k!='sha256'}
            if hashlib.sha256(canonical(body)).hexdigest()!=row['sha256']:raise ValueError('Registry audit checksum changed')
            result.append(row)
        return result
    def state(self):
        state={slot:{'model':'reference_v15','validated':False,'reason':'Preserved reference; superiority has not been established.'} for slot in SLOTS}
        for event in self.events():
            if event['kind'] in ('promote','rollback'):state[event['slot']]={'model':event['model'],'validated':True,'event':event['sha256']}
        return state
    def _append(self,body):
        body={**body,'sequence':len(self.events())};sha=hashlib.sha256(canonical(body)).hexdigest();body['sha256']=sha
        p=self.path/(str(body['sequence']).zfill(6)+'-'+sha+'.json')
        with p.open('x') as f:json.dump(body,f,sort_keys=True,allow_nan=False)
        return body
    def evaluate(self,slot,model,result,gate,expected_champion,allow_promotion=False):
        if slot not in SLOTS:raise ValueError('Unknown independent champion slot')
        with self.locked():
            if self.state()[slot]['model']!=expected_champion:raise ValueError('Champion changed; re-evaluation required')
            reasons=promotion_reasons(result,gate)
            if not allow_promotion:reasons.append('research_candidate_not_enabled_for_live_promotion')
            return self._append({'kind':'reject' if reasons else 'promote','slot':slot,'model':model,'previous':expected_champion,'result':result,'reasons':reasons})
    def rollback(self,slot,target,expected_champion):
        with self.locked():
            if slot not in SLOTS or self.state()[slot]['model']!=expected_champion:raise ValueError('Champion changed')
            if not any(e['kind']=='promote' and e['slot']==slot and e['model']==target for e in self.events()):raise ValueError('Rollback requires an earlier validated model in the same slot')
            return self._append({'kind':'rollback','slot':slot,'model':target,'previous':expected_champion})

class BoundedLoop:
    """No unbounded retraining; isolated per-slot plateau and global CPU budgets."""
    def __init__(self,cpu_budget,max_iterations=3,patience=2):self.budget=cpu_budget;self.max_iterations=max_iterations;self.patience=patience;self.steps=[];self.failures={s:0 for s in SLOTS}
    def next(self,slot,spent_cpu,data_qualified=True):
        if spent_cpu>=self.budget:return False,'compute_budget_exhausted'
        if not data_qualified:return False,'point_in_time_data_limitation'
        if self.failures[slot]>=self.patience:return False,'slot_validation_plateau'
        if sum(s['slot']==slot for s in self.steps)>=self.max_iterations:return False,'predeclared_candidates_exhausted'
        return True,None
    def record(self,slot,model,improved):
        self.steps.append({'slot':slot,'model':model,'improved':bool(improved)});self.failures[slot]=0 if improved else self.failures[slot]+1
