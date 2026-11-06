"""Publication-aware evidence ledger. Retrieval time never substitutes for publication.
Provider snapshots and official confirmation have distinct confidence statuses.
Current mutable documents revised after kickoff are rejected for that forecast.
"""
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from hashlib import sha256
import json,math
from urllib.parse import urlparse

KINDS=('starting_quarterback','injury','starting_lineup','depth_chart','availability','snap_counts','participation','offense','defense','coaching','weather_forecast','roster_transaction','matchup')
CONFIDENCE=('official_confirmed','provider_snapshot','historical_statistic','unverified_timestamp','missing')
def aware(v):
    d=datetime.fromisoformat(str(v).replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('An explicit publication timezone is required')
    return d.astimezone(timezone.utc)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
@dataclass(frozen=True)
class Evidence:
    sport:str
    kind:str
    source:str
    source_sha256:str
    retrieved_at:str
    confidence:str
    value:dict
    team_id:str|None=None
    player_id:str|None=None
    event_id:str|None=None
    published_at:str|None=None
    modified_at:str|None=None
    observed_at:str|None=None
    missing_reason:str|None=None
    def __post_init__(self):
        if self.sport not in ('NFL','CFB','NBA') or self.kind not in KINDS or self.confidence not in CONFIDENCE:raise ValueError('Unsupported evidence identity/type')
        if self.confidence!='missing' and (urlparse(self.source).scheme!='https' or len(self.source_sha256)!=64):raise ValueError('A source and content checksum are required')
        aware(self.retrieved_at)
        for x in (self.published_at,self.modified_at,self.observed_at):
            if x:aware(x)
        if self.confidence in ('official_confirmed','provider_snapshot') and not self.published_at:raise ValueError('Verified evidence requires a publication/snapshot timestamp')
        if self.published_at and aware(self.published_at)>aware(self.retrieved_at):raise ValueError('Publication cannot follow retrieval')
        if self.modified_at and aware(self.modified_at)>aware(self.retrieved_at):raise ValueError('Modification cannot follow retrieval')
        if self.modified_at and self.published_at and aware(self.modified_at)<aware(self.published_at):raise ValueError('Modification precedes publication')
        canonical(asdict(self))
    @property
    def id(self):
        # Re-fetches preserve semantic identity; retrieval is provenance, not a fact.
        d=asdict(self);d.pop('retrieved_at');return sha256(canonical(d)).hexdigest()
    def for_prediction(self,sport,event_id,team_ids,cutoff,strict=True):
        if self.sport!=sport or (self.event_id and self.event_id!=event_id) or (self.team_id and self.team_id not in team_ids):return False,'identity_scope_mismatch'
        if self.confidence in ('missing','unverified_timestamp'):return False,self.missing_reason or 'publication_timestamp_unverified'
        if not self.published_at:return False,'publication_timestamp_missing'
        t=aware(cutoff)
        if max(aware(x) for x in [self.published_at,self.modified_at or self.published_at])>=t:return False,'published_or_revised_after_cutoff'
        if self.observed_at and aware(self.observed_at)>=t:return False,'future_observation'
        if strict and self.confidence=='historical_statistic':return False,'original_statistics_publication_unverified'
        return True,None
    def json(self):return {'id':self.id,**asdict(self)}

def reconstruct(records,sport,event_id,team_ids,cutoff):
    accepted=[];rejected=[]
    for r in records:
        ok,why=r.for_prediction(sport,event_id,team_ids,cutoff)
        (accepted if ok else rejected).append(r.json() if ok else {'id':r.id,'kind':r.kind,'reason':why})
    coverage={k:{'status':'available' if any(r['kind']==k for r in accepted) else 'missing','records':sum(r['kind']==k for r in accepted)} for k in KINDS}
    # An official report for one player does not establish a complete roster.
    return {'sport':sport,'eventId':event_id,'cutoff':cutoff,'accepted':accepted,'rejected':rejected,'coverage':coverage,'injuriesComplete':False,'lineupConfirmed':all(any(r['kind']=='starting_lineup' and r['team_id']==team and r['confidence']=='official_confirmed' and r['value'].get('complete') is True for r in accepted) for team in team_ids),'missingAvailabilityMeansHealthy':False,'sha256':sha256(canonical([r['id'] for r in accepted])).hexdigest()}

def scenario_weights(records,sport,event_id,team_ids,cutoff):
    context=reconstruct(records,sport,event_id,team_ids,cutoff)
    result={}
    for r in context['accepted']:
        if r['kind'] not in ('availability','injury') or not r.get('player_id'):continue
        status=str(r['value'].get('status','')).lower()
        if status in ('out','inactive','injured_reserve'):w={'active':0.,'limited':0.,'inactive':1.}
        elif status=='active_unrestricted' and r['confidence']=='official_confirmed':w={'active':1.,'limited':0.,'inactive':0.}
        else:w=None
        result[r['player_id']]={'status':status,'weights':w,'scenarios':['active','limited','inactive'] if w is None else [k for k,v in w.items() if v], 'reason':'Separate unweighted scenarios; no calibrated league-specific availability model is available.' if w is None else 'Explicit verified status; active does not imply unrestricted without confirmation.'}
    return result
