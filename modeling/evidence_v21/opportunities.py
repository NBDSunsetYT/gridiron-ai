"""League-specific coherent mean projections. No simulated samples invented."""
from collections import defaultdict
import numpy as np
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.linear_model import Ridge,LogisticRegression
from scipy.sparse import csr_matrix,hstack
from ..accuracy_v20.quality import aware
from datetime import timedelta
from ..structural_v18.models import Projection
VERSION='lineup-and-team-budget-heads-21.0.0'
def capped_budget(values,total,cap):
    v=np.asarray(values,float)
    if np.any(~np.isfinite(v)) or total<0 or cap<=0 or len(v)*cap<total:raise ValueError('Supported roster cannot satisfy team opportunity budget')
    lo,hi=-cap-float(np.max(v)),cap+total+float(np.max(abs(v)))
    for _ in range(70):
        mid=(lo+hi)/2
        if np.clip(v+mid,0,cap).sum()<total:lo=mid
        else:hi=mid
    result=np.clip(v+(lo+hi)/2,0,cap)
    if abs(result.sum()-total)>1e-7:raise AssertionError('Team budget failed to reconcile')
    return result
class LineupMinutes:
    """Observed prior starts inform uncertain workload, never a confirmed lineup."""
    def fit(self,rows,cutoff):
        rows=[r for r in rows if r['stat']=='minutes' and r['player']!='__team__']
        if len(rows)<100 or any(aware(r['at'])>=aware(cutoff) for r in rows):raise ValueError('Earlier minutes training rows required')
        self.cutoff=cutoff;self.names=rows[0]['featureNames'];self.scaler=StandardScaler().fit([r['x'] for r in rows]);x=self.scaler.transform([r['x'] for r in rows]);y=np.asarray([r['y'] for r in rows]);self.presence=LogisticRegression(C=.05,max_iter=300,random_state=21021).fit(x,y>0) if len(set(y>0))>1 else None
        pos=y>0;self.encoding=OneHotEncoder(handle_unknown='ignore').fit([[r['player'],r['team']] for r in rows]);z=hstack([csr_matrix(x),self.encoding.transform([[r['player'],r['team']] for r in rows])],format='csr');self.volume=Ridge(alpha=100,solver='lsqr').fit(z[pos],y[pos]);starts=np.asarray([r.get('actualStarter') is True for r in rows]);self.start_probability=None;self.states={}
        if len(set(starts[pos]))>1:self.start_probability=LogisticRegression(C=.05,max_iter=300,random_state=21021).fit(x[pos],starts[pos])
        for state in (False,True):
            use=pos&(starts==state)
            if use.sum()>=30:self.states[state]=Ridge(alpha=100,solver='lsqr').fit(z[use],y[use])
        self.source='Earlier actual starting states fit conditional workload heads. Upcoming starter state is uncertain unless a verified pregame announcement is supplied.';return self
    def predict_team(self,rows,inactive=(),expected_team_minutes=240.,lineup_fact=None):
        if any(aware(r['at'])<=aware(self.cutoff) for r in rows):raise ValueError('Prediction must follow training')
        x=self.scaler.transform([r['x'] for r in rows]);z=hstack([csr_matrix(x),self.encoding.transform([[r['player'],r['team']] for r in rows])],format='csr');p=self.presence.predict_proba(x)[:,1] if self.presence is not None else np.ones(len(rows));raw=np.maximum(0,self.volume.predict(z))*p
        if self.start_probability is not None and len(self.states)==2:
            start=self.start_probability.predict_proba(x)[:,1]
            if lineup_fact is not None:
                cutoff=aware(rows[0].get('predictionAsOf')) if rows[0].get('predictionAsOf') else aware(rows[0]['at'])-timedelta(minutes=30)
                if lineup_fact.get('kind')!='confirmed_starting_lineup' or lineup_fact.get('eventId')!=rows[0]['gameId'] or not lineup_fact.get('sourceVersion') or not str(lineup_fact.get('source','')).startswith('https://') or aware(lineup_fact['publishedAt'])>cutoff or (lineup_fact.get('modifiedAt') and aware(lineup_fact['modifiedAt'])>cutoff) or len(set(lineup_fact.get('players',[])))!=5:raise ValueError('Verified event-specific lineup available by the prediction cutoff required; final starters are not pregame evidence')
                start=np.asarray([float(r['player'] in lineup_fact['players']) for r in rows])
            raw=p*(start*np.maximum(0,self.states[True].predict(z))+(1-start)*np.maximum(0,self.states[False].predict(z)))
        keep=np.asarray([r['player'] not in inactive for r in rows]);result=np.zeros(len(rows));result[keep]=capped_budget(raw[keep],expected_team_minutes,expected_team_minutes/5)
        return result
class FootballShares:
    """Separate team opportunity budgets and observed player share/efficiency.

    A Dirichlet posterior includes zero-usage prior appearances. Allocation is
    uncertain and conditional on the prior-known participant universe, not a
    claim that an unknown injured player is active.
    """
    def __init__(self,sport):
        if sport not in ('NFL','CFB'):raise ValueError('Separate football league required')
        self.sport=sport
    def fit(self,rows,cutoff):
        if any(aware(r['at'])>=aware(cutoff) for r in rows):raise ValueError('Future training row')
        self.cutoff=cutoff;self.team={};self.rate={};self.teamsample=defaultdict(list);grouped=defaultdict(list)
        for r in rows:grouped[(r['player']=='__team__',r['stat'])].append(r)
        for stat in ('passingAttempts','targets','carries'):
            rs=grouped.get((True,stat),[])
            if len(rs)>=30:self.team[stat]=Projection('ridge').fit(rs)
        for stat,op in [('passingYards','passingAttempts'),('receivingYards','targets'),('receptions','targets'),('rushingYards','carries')]:
            rs=[r for r in grouped.get((False,stat),[]) if r['opportunity']>0]
            if len(rs)>=100:
                scaler=StandardScaler().fit([r['x'] for r in rs]);fit=Ridge(alpha=100,solver='lsqr').fit(scaler.transform([r['x'] for r in rs]),[r['y']/r['opportunity'] for r in rs],sample_weight=np.sqrt([r['opportunity'] for r in rs]));self.rate[stat]=(scaler,fit)
        return self
    def predict_team(self,rows,inactive=()):
        if any(aware(r['at'])<=aware(self.cutoff) for r in rows):raise ValueError('Pregame head cutoff violated')
        groups=defaultdict(list)
        for r in rows:groups[r['stat']].append(r)
        out={};budgets={}
        for stat in ('passingAttempts','carries','targets'):
            team=[r for r in groups[stat] if r['player']=='__team__'];rs=[r for r in groups[stat] if r['player']!='__team__' and not r['player'].split(':')[-1].startswith('-') and r['x'][r['featureNames'].index('target_mean8')]>0]
            if stat not in self.team or not team or not rs:continue
            total=float(self.team[stat].predict(team)[0]);total=min(total,budgets['passingAttempts']) if stat=='targets' and 'passingAttempts' in budgets else total;budgets[stat]=total
            # Five prior appearances plus a documented Jeffreys Dirichlet
            # half-count, only among historically supported role participants.
            shares=np.asarray([5*max(0,r['baseline']) if r['player'] not in inactive else 0 for r in rs]);eligible=np.asarray([r['player'] not in inactive for r in rs]);shares=shares+eligible*.5
            if shares.sum()==0:raise ValueError('No supported participant after verified exclusions')
            for r,v in zip(rs,total*shares/shares.sum()):out[(r['player'],stat)]=float(v)
        for stat,op in [('passingYards','passingAttempts'),('receivingYards','targets'),('receptions','targets'),('rushingYards','carries')]:
            rs=[r for r in groups[stat] if (r['player'],op) in out]
            if stat not in self.rate or not rs:continue
            scaler,fit=self.rate[stat];rates=np.maximum(0,fit.predict(scaler.transform([r['x'] for r in rs])))
            if stat=='receptions':rates=np.minimum(1,rates)
            for r,v in zip(rs,rates):out[(r['player'],stat)]=float(out[(r['player'],op)]*v)
        passing=sum(v for (p,s),v in out.items() if s=='passingYards');receivers=[k for k in out if k[1]=='receivingYards'];raw=sum(out[k] for k in receivers)
        if passing and receivers and raw:
            for k in receivers:out[k]*=passing/raw
        if receivers and abs(sum(out[k] for k in receivers)-passing)>1e-6:raise AssertionError('Mean passing/receiving yards do not reconcile')
        return out,{'teamBudgets':budgets,'version':VERSION,'conditionalOnPriorKnownRoster':True,'injuryWeightsInvented':False,'fullGameSimulations':0}
