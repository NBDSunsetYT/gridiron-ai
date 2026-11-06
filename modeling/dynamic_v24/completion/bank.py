"""Load content-verified specialized research heads and bind them to game events.

Only locally generated, checksum-addressed research pickles are accepted. This
module is never exposed as a model-upload API. Marginal conditional candidates
do not acquire strict joint eligibility by passing through the bank.
"""
from pathlib import Path
import hashlib,pickle
import numpy as np
from ...accuracy_v20.quality import aware
from ...fullgame_v23.modes import Mode
from ...overnight_v20.state import read,digest
from .data import LABELS
from .joint import HeadFootballKernel,football_mechanics,nba_rates,nba_mechanics

class HeadBank:
    def __init__(self,manifest,root):
        self.root=Path(root).resolve();self.manifest=read(manifest) if isinstance(manifest,(str,Path)) else manifest
        if self.manifest.get('sha256')!=digest({k:v for k,v in self.manifest.items() if k!='sha256'}):raise ValueError('Model-bank manifest checksum mismatch')
        self.loaded={}
    def load(self,entry):
        path=(self.root/entry['modelPath']).resolve()
        if not path.is_relative_to(self.root/'artifacts/dynamic-v24') or path.suffix!='.pickle':raise ValueError('Only owned research model artifacts are loadable')
        if entry['modelSHA256'] not in self.loaded:
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=entry['modelSHA256']:raise ValueError('Specialized model checksum mismatch')
            model=pickle.loads(raw)
            if model.estimand!='conditional_mean':raise ValueError('Medians/probabilities cannot masquerade as expected-value heads')
            self.loaded[entry['modelSHA256']]=model
        model=self.loaded[entry['modelSHA256']]
        if model.stat!=entry['stat']:raise ValueError('Model artifact statistic differs from its manifest')
        return model
    def bundle(self,sport,rows,as_of,ctx,*,registry=None,qualification=None):
        if ctx.get('sport')!=sport or any(r.get('sport',sport)!=sport or r.get('gameId')!=ctx['eventId'] for r in rows):raise ValueError('Exact sport and event mapping required')
        if any(k in r for r in rows for k in LABELS):raise ValueError('Outcomes cannot enter the model bank')
        if len({(r['gameId'],r.get('team'),r['player'],r['stat']) for r in rows})!=len(rows):raise ValueError('Duplicate player/stat evidence')
        if any(not r.get('featureLastGame') or aware(r['featureLastGame'])>=aware(as_of) for r in rows):raise ValueError('Only earlier verified history timestamps are usable')
        if ctx['mode']!=Mode.MECHANICS and any(not r.get('at') or aware(as_of)>aware(r['at']) for r in rows):raise ValueError('Postgame research cutoffs cannot masquerade as pregame inputs')
        allowed=None
        if ctx['mode']==Mode.FORECAST:
            if registry is None or not qualification:raise ValueError('Strict specialized selection requires qualified registry and joint certificate')
            if aware(as_of)!=aware(ctx['cutoff']):raise ValueError('Model-bank cutoff differs from strict forecast')
            admitted=registry.joint_heads(sport,**qualification);allowed={r['id'] for r in admitted.values()}
        elif ctx['mode'] not in (Mode.MECHANICS,Mode.CONDITIONAL):raise ValueError('Explicit research mode required')
        output={};team_output={};player_teams={};chosen=[];withheld=[]
        for stat in sorted({r['stat'] for r in rows}):
            entries=[e for e in self.manifest['heads'] if e['sport']==sport and e['stat']==stat and aware(e['availableAfter'])<aware(as_of) and (allowed is None or e.get('registryRecordId') in allowed)]
            if not entries:withheld.append({'stat':stat,'reason':'No appropriate head fit/selection precedes cutoff'});continue
            entry=max(entries,key=lambda e:(aware(e['availableAfter']),aware(e.get('trainingThrough',e['availableAfter'])),e['modelVersion']));frame=[r for r in rows if r['stat']==stat]
            if allowed is not None and entry['modelSHA256'] not in admitted[stat]['modelSHA256']:raise ValueError('Model artifact differs from qualified registry version')
            model=self.load(entry);pred=model.predict(frame)
            if len(pred)!=len(frame) or not np.all(np.isfinite(pred)):raise ValueError('Invalid specialized expected-value output')
            for r,value in zip(frame,pred):
                if r['player']=='__team__':team_output.setdefault(r['team'],{})[stat]=float(value);continue
                if r['player'] in player_teams and player_teams[r['player']]!=r.get('team'):raise ValueError('Player maps to two teams in the same event; roster evidence required')
                player_teams[r['player']]=r.get('team');output.setdefault(r['player'],{})[stat]=float(value)
            chosen.append({'stat':stat,'modelVersion':entry['modelVersion'],'modelSHA256':entry['modelSHA256'],'role':entry['role'],'registryRecordId':entry.get('registryRecordId')})
        return {'estimates':output,'teamEstimates':team_output,'playerTeams':player_teams,'manifest':{'sport':sport,'eventId':ctx['eventId'],'asOf':as_of,'estimand':'conditional_mean','modelVersions':[e['modelVersion'] for e in chosen],'headIds':[e['registryRecordId'] for e in chosen if e['registryRecordId']],'heads':chosen,'productionPromotion':False,'jointAccuracyValidated':ctx['mode']==Mode.FORECAST,'missingAvailabilityIsHealthy':False},'withheld':withheld}

def football_from_bank(bank,sport,rows,as_of,ctx,teams,play_rows,owners,season,*,games=4,seed=240246,conversions=None,clock_model=None,additional_clock_pools=None):
    if ctx['mode']!=Mode.MECHANICS:raise ValueError('Uncertified mechanics bank path cannot run a forecast')
    bundle=bank.bundle(sport,rows,as_of,ctx);kernel=HeadFootballKernel(sport,teams,play_rows,owners,estimates=bundle['estimates'],head_manifest=bundle['manifest'],clock_model=clock_model,additional_clock_pools=additional_clock_pools)
    return football_mechanics(kernel,ctx,season,games=games,seed=seed,conversions=conversions)

def nba_from_bank(bank,rows,as_of,ctx,base,*,games=4,seed=240246,clock_intervals=None):
    if ctx['mode']!=Mode.MECHANICS:raise ValueError('Uncertified NBA bank path cannot run a forecast')
    bundle=bank.bundle('NBA',rows,as_of,ctx);rates=nba_rates(base,bundle['estimates'],bundle['manifest'],ctx)
    return nba_mechanics(rates,ctx,games=games,seed=seed,clock_intervals=clock_intervals)
