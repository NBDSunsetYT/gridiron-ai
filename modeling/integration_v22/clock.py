"""Runtime form of V21's fitted interval-censored clock, without refitting it."""
import numpy as np
from ..accuracy_v20.quality import aware
KINDS=('pass','rush','punt','field_goal','kneel','penalty','sack')
def serialize_clock(fitted):
    return {'version':fitted.metadata['version'],'metadata':fitted.metadata,'globalMass':fitted.global_mass.tolist(),'supported':sorted(fitted.supported),'pools':[{'kind':k[0],'complete':k[1],'hurry':k[2],'mass':p.tolist()} for k,p in sorted(fitted.pools.items())],'administrative':None,'timingRegimeValidated':False}
class RuntimeClock:
    def __init__(self,artifact,event_start):
        self.artifact=artifact
        if aware(artifact['metadata']['fitCutoff'])>=aware(event_start):raise ValueError('Clock fit must precede the forecast')
        self.pools={(r['kind'],r['complete'],r['hurry']):np.asarray(r['mass'],float) for r in artifact['pools']};self.global_mass=np.asarray(artifact['globalMass'],float)
        for p in [self.global_mass,*self.pools.values()]:
            if len(p)!=91 or not np.all(np.isfinite(p)) or np.any(p<0) or abs(p.sum()-1)>1e-6 or p[0]!=0:raise ValueError('Timed clock masses must be normalized with no zero charge')
    def cdf(self,kind,complete,hurry):
        if kind=='penalty':
            a=self.artifact.get('administrative')
            if not a or a.get('verified') is not True or not a.get('sourceVersion'):raise ValueError('Administrative clock evidence unavailable; zero runoff is not assumed')
            p=np.asarray(a['mass'],float)
            if len(p)!=91 or np.any(p<0) or not np.all(np.isfinite(p)) or abs(p.sum()-1)>1e-6:raise ValueError('Invalid administrative clock distribution')
        else:
            if kind not in self.artifact['supported']:raise ValueError('Clock evidence unavailable for '+kind)
            p=self.pools.get((kind,bool(complete),bool(hurry)),self.global_mass)
        c=np.cumsum(p);c[-1]=1;return c
    def sample(self,rng,kinds,complete,hurry,active):
        out=np.zeros(len(kinds),int)
        # Draw only for active games and supported contexts. Unsupported
        # administrative events never inherit the global timed-play fallback.
        for k,c,h in sorted(set(zip(kinds[active].tolist(),complete[active].tolist(),hurry[active].tolist()))):
            use=active&(kinds==k)&(complete==c)&(hurry==h);out[use]=np.searchsorted(self.cdf(KINDS[k],c,h),rng.random(use.sum()),side='right')
        timed=active&(kinds!=KINDS.index('penalty'))
        if np.any(out[timed]<=0):raise AssertionError('A completed timed play consumed zero game-clock seconds')
        return out
