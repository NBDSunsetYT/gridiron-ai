"""Independent rebound projection heads on identified historical floor exposure."""
from collections import defaultdict
import numpy as np
from ..nba_v15 import beta_prior
from ..accuracy_v20.quality import aware
class CourtRebounds:
    def __init__(self,use_court=True):self.use_court=use_court
    def fit(self,games,exposures,cutoff):
        totals={s:defaultdict(lambda:np.zeros(3)) for s in ['offensive_rebounds','defensive_rebounds']};used=[]
        for g in games:
            if aware(g['at'])>=aware(cutoff):raise ValueError('Future actual exposure cannot train a pregame projection')
            exp=exposures.get(g['id'])
            if not exp or not exp['complete']:continue
            used.append(g['id'])
            for p in g['players']:
                pid=str(int(p['athlete_id']));team=str(p['team_id']);minutes=float(p.get('minutes') or 0);opp=g['teams'][team]['opponent_team_id'];opponent=g['teams'].get(str(opp))
                if minutes<=0 or not opponent:continue
                duration=sum(float(v.get('minutes') or 0) for v in g['players'] if str(v['team_id'])==team)/5
                for stat,other in [('offensive_rebounds','defensive_rebounds'),('defensive_rebounds','offensive_rebounds')]:
                    proxy=(float(g['teams'][team][stat])+float(opponent[other]))*minutes/duration;observed=exp['players'][pid]['exposure'].get(stat,0);trials=float(observed) if self.use_court else proxy;count=float(p.get(stat) or 0)
                    if trials<count:continue
                    totals[stat][pid]+=np.array([count,trials,proxy])
        self.posterior={};self.priors={};self.density={};self.games=used
        for stat,values in totals.items():
            vals=np.asarray(list(values.values()));valid=vals[:,1]>0;a,b=beta_prior(vals[valid,0],vals[valid,1]);self.priors[stat]=(a,b);self.posterior[stat]={pid:(v[0]+a)/(v[1]+a+b) for pid,v in values.items()};self.density[stat]={pid:(v[1]+20)/(v[2]+20) if self.use_court else 1. for pid,v in values.items()}
        if len(used)<5:raise ValueError('At least five independently reconciled earlier exposure games required')
        return self
    def predict_team(self,player_minutes,own,opponents):
        if not own or not opponents:raise ValueError('Earlier opponent-adjusted team rebound evidence required')
        result={p:0. for p in player_minutes};detail={};duration=sum(player_minutes.values())/5
        for stat,other in [('offensive_rebounds','defensive_rebounds'),('defensive_rebounds','offensive_rebounds')]:
            own_op=[float(t[stat])+float(o[other]) for t,o in own];opp_op=[float(t[other])+float(o[stat]) for t,o in opponents];opportunities=.5*(np.mean(own_op)+np.mean(opp_op));capture=.5*(sum(float(t[stat]) for t,o in own)/sum(own_op)+sum(float(o[stat]) for t,o in opponents)/sum(opp_op));budget=float(opportunities*capture);a,b=self.priors[stat];raw={p:opportunities*m/duration*self.density[stat].get(p,1.)*self.posterior[stat].get(p,a/(a+b)) for p,m in player_minutes.items()};normal=sum(raw.values())
            if normal<=0:raise ValueError('No supported conditional rebound exposure')
            for p,v in raw.items():result[p]+=budget*v/normal
            detail[stat]={'predictedReboundableOpportunities':float(opportunities),'teamReboundMean':budget,'playerMeans':{p:budget*v/normal for p,v in raw.items()},'exposure':'identified earlier on-court board events with regularized future exposure density' if self.use_court else 'team board opportunities times minutes proxy'}
        return result,detail
