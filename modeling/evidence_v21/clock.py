"""Interval-censored clock measurements, not invented observed snap times.

An independently checked drive clock constrains a sum of uncertain durations.
Dynamic programming conditions categorical timing laws on that sum. Regulation
clocks are distinct from real wall time; no-play administrative events can take
zero game-clock seconds. Completed timed plays cannot.
"""
from collections import defaultdict
import math,copy
import numpy as np
from ..accuracy_v20.quality import aware
VERSION='interval-censored-drive-clock-21.0.0'
def seconds(text):
    parts=str(text).split(':')
    if len(parts)!=2:raise ValueError('MM:SS clock required')
    m,s=map(int,parts)
    if not 0<=s<60 or not 0<=m<=60:raise ValueError('Invalid clock')
    return 60*m+s
def regulation_clock(period,clock):
    if period not in (1,2,3,4) or not 0<=clock<=900:raise ValueError('Regulation period/clock required')
    return (4-period)*900+clock
def context(play):return (play['kind'],bool(play.get('complete')),bool(play.get('hurry')))
def conditional_intervals(probabilities,total,seed=None,samples=0):
    """Exact marginal laws and optional joint draws, conditional on anchor sum."""
    ps=[np.asarray(p,float) for p in probabilities]
    if not ps or len(ps)>60 or not isinstance(total,int) or not 0<=total<=900:raise ValueError('Bounded regulation timing block required')
    if any(p.ndim!=1 or len(p)!=91 or np.any(~np.isfinite(p)) or np.any(p<0) or p.sum()<=0 for p in ps):raise ValueError('Valid 0..90-second timing masses required')
    ps=[p/p.sum() for p in ps];one=np.zeros(total+1);one[0]=1.;forward=[one];scales=[]
    for p in ps:
        v=np.convolve(forward[-1],p)[:total+1];z=v.sum()
        if not z:raise ValueError('Timing anchors contradict play support')
        forward.append(v/z);scales.append(z)
    if forward[-1][total]<=0:raise ValueError('No supported joint timing allocation matches these anchors')
    backward=[None]*(len(ps)+1);backward[-1]=one
    for i in range(len(ps)-1,-1,-1):
        v=np.convolve(ps[i],backward[i+1])[:total+1];backward[i]=v/v.sum()
    marginals=[]
    for i,p in enumerate(ps):
        v=np.zeros(91)
        for d in range(min(90,total)+1):v[d]=p[d]*np.dot(forward[i][:total-d+1],backward[i+1][:total-d+1][::-1])
        if v.sum()<=0:raise ValueError('Unstable timing posterior')
        marginals.append(v/v.sum())
    draws=[];rng=np.random.default_rng(seed)
    for _ in range(samples):
        remaining=total;draw=[]
        for i,p in enumerate(ps):
            v=np.zeros(91);ds=np.arange(min(90,remaining)+1);v[ds]=p[ds]*backward[i+1][remaining-ds];v/=v.sum();d=int(rng.choice(91,p=v));draw.append(d);remaining-=d
        if remaining:raise AssertionError('Clock conservation failed')
        draws.append(draw)
    means=[float(p@np.arange(91)) for p in marginals]
    if abs(sum(means)-total)>1e-6:raise AssertionError('Marginal clock means do not reconcile')
    return {'masses':[p.tolist() for p in marginals],'meanSeconds':means,'interval90':[[int(np.searchsorted(np.cumsum(p),q)) for q in (.05,.95)] for p in marginals],'jointDraws':draws,'totalSeconds':total,'sumConserved':True,'logAnchorMass':float(math.log(forward[-1][total])+sum(math.log(z) for z in scales)),'interpretation':'Latent interval-censored durations, not exact observed play runoff. Joint draws preserve the shared anchor constraint.'}
class CensoredClock:
    def fit(self,blocks,cutoff,iterations=2):
        if iterations not in (0,1,2):raise ValueError('Predeclared bounded EM passes only')
        if not blocks or any(aware(b['eventEnd'])>=aware(cutoff) for b in blocks):raise ValueError('Earlier completed training blocks required')
        counts=defaultdict(lambda:np.zeros(91));global_count=np.zeros(91);trusted=0
        for b in blocks:
            intervals=b.get('observedInterEventIntervals') or b.get('exactIntervals')
            if intervals:
                for p,d in zip(b['plays'],intervals):
                    if 1<=d<=90:counts[context(p)][d]+=1;global_count[d]+=1;trusted+=1
        if trusted<100:raise ValueError('At least 100 observed positive timing intervals required; no invented timing prior')
        global_count[0]=0;global_mass=global_count/global_count.sum();self.pools={k:(v+5*global_mass)/(v.sum()+5) for k,v in counts.items()};self.global_mass=global_mass
        self.supported=set(p['kind'] for b in blocks for p in b['plays']);self.failures=[]
        for _ in range(iterations):
            soft=defaultdict(lambda:np.zeros(91))
            for b in blocks:
                try:post=conditional_intervals([self.mass(p) for p in b['plays']],b['elapsedSeconds'])
                except ValueError as e:self.failures.append({'blockId':b['id'],'reason':str(e)});continue
                for p,v in zip(b['plays'],post['masses']):soft[context(p)]+=v
            self.pools={k:(v+5*self.global_mass)/(v.sum()+5) for k,v in soft.items()}
        self.metadata={'version':VERSION,'fitCutoff':cutoff,'trainingGames':sorted({b['eventId'] for b in blocks}),'trainingBlocks':len(blocks),'observedPositiveInterEventIntervals':trusted,'timingUnit':'Effective game-clock charge per sequenced action including between-action runoff. Raw event clock conventions do not establish physical live-ball durations.','emPasses':iterations,'failedBlockUpdates':len(self.failures),'exactIndividualTimesClaimed':False,'scoreInputs':False,'productionEligible':False};return self
    def mass(self,play):
        if play['kind']=='administrative':
            if play.get('zeroClockExplicitlyVerified') is not True:raise ValueError('Administrative runoff is unresolved; zero cannot be assumed')
            v=np.zeros(91);v[0]=1;return v
        if play['kind'] not in self.supported:raise ValueError('Unsupported timed-play kind')
        return self.pools.get(context(play),self.global_mass).copy()
    def reconstruct(self,block,seed=21021,samples=0):
        if block.get('sequenceVerified') is not True or block.get('anchorVerified') is not True:raise ValueError('Independently verified sequence and timing anchors required')
        return {**conditional_intervals([self.mass(p) for p in block['plays']],block['elapsedSeconds'],seed,samples),'blockId':block['id'],'sources':block['sources'],'modelVersion':VERSION}
    def forecast_seconds(self,plays):
        return float(sum(self.mass(p)@np.arange(91) for p in plays))
