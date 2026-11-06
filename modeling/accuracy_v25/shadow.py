"""Three objective views over one immutable existing forecast realization tape.

Marginal V24 draws stay marginal diagnostics: sharing them across objectives is
not proof of a jointly coherent game. Strict joint forecasting remains gated.
"""
from copy import deepcopy
import numpy as np
from .objectives import AccuracyMode, score_numerical, score_probability, stamp_mode
from .market_research import compare_market
from ..overnight_v20.state import digest


class FrozenShadow:
    def __init__(self, identities, point, draws, *, model_version, provenance,
                 scope='conditional_corrected_history', joint=False, qualification=None):
        keys=[(r['sport'],r['gameId'],r['team'],r['player'],r['stat']) for r in identities]
        if not keys or len(set(keys))!=len(keys):raise ValueError('Unique exact league/event/team/player/stat identities required')
        if any(any(k in r for k in ('y','actualMinutes','finalScore')) for r in identities):
            raise ValueError('Outcome labels cannot enter frozen forecast identities')
        if scope not in ('conditional_corrected_history','strict_pregame'):
            raise ValueError('Explicit evaluation evidence tier required')
        if scope=='strict_pregame':
            if not joint or not qualification:raise ValueError('Strict forecasts require the existing joint qualification')
            from ..fullgame_v23.forecast import require
            from ..dynamic_v24.completion.selection import joint_probability_gate
            require(**qualification);joint_probability_gate(qualification['model'],qualification['match'],qualification['certificate'])
        p,x=np.array(point,float,copy=True),np.array(draws,float,copy=True)
        if p.shape!=(len(keys),) or x.ndim!=2 or x.shape[0]!=len(keys) or x.shape[1]<2 or not np.isfinite(p).all() or not np.isfinite(x).all():
            raise ValueError('Aligned actual forecast points and realizations required')
        if not provenance.get('sourceModelSHA256') or not provenance.get('sourceForecastSHA256'):
            raise ValueError('Original fitted model and frozen forecast editions required')
        p.flags.writeable=False;x.flags.writeable=False
        self._point=p;self._draws=x;self.identities=deepcopy(identities);self.keys=keys
        self.model_version=model_version;self.scope=scope;self.joint=joint
        self.snapshot={'identities':deepcopy(identities),'pointHash':digest(p.tolist()),
                       'realizationsHash':digest(x.tolist()),'modelVersion':model_version,
                       'provenance':deepcopy(provenance),'scope':scope,'jointRealizations':joint,
                       'drawCountPerObservation':x.shape[1]}
        self.snapshot_hash=digest(self.snapshot);self.event_hash=digest(sorted({(r['sport'],r['gameId']) for r in identities}))

    def evaluate(self, observed, *, thresholds=(), markets=None):
        keys=[(r['sport'],r['gameId'],r['team'],r['player'],r['stat']) for r in observed]
        if keys!=self.keys:raise ValueError('Outcome identities/order differ from the frozen forecast')
        y=np.asarray([r['y'] for r in observed],float)
        numerical=score_numerical(y,self._point,self._draws)
        if all(r['stat'] in ('moneyline','doubleDouble','tripleDouble') for r in observed):
            probability=score_probability(y,self._point)|{'scope':'raw_bernoulli_not_approved_calibration'}
        elif thresholds:
            n=self._draws.shape[1];probabilities=[];truth=[]
            for t in thresholds:
                probabilities.extend((np.sum(self._draws<=t,axis=1)+.5)/(n+1))
                truth.extend(y<=t)
            probability=score_probability(truth,probabilities)|{'scope':'training_quantile_CDF_diagnostic_not_verified_market_line','thresholds':list(thresholds)}
        else:probability={'brier':None,'logLoss':None,'ece':None,'scope':'no_verified_binary_definition'}
        probability|={'crps':numerical['crps'],'calibratedProbability':None}
        if markets is None:
            market={'status':'market_data_unavailable','observations':0,'clv':None,'returnDistribution':None,
                    'marketProbability':None,'blendWeight':None,'marketEdgeModel':None}
        else:
            if len(markets)!=len(self.keys):raise ValueError('Market observations cannot select a different event cohort')
            # A/B/C keep all event identities even if only a subset has quotes.
            # No arbitrary line is extracted from a training diagnostic grid.
            rows=[]
            from .objectives import threshold_probability
            for i,m in enumerate(markets):
                if m is None:rows.append(None);continue
                identity=m['identity'];row=observed[i]
                if not self.identities[i].get('forecastAt') or m.get('forecastAt')!=self.identities[i]['forecastAt'] or m.get('eventAt')!=self.identities[i].get('eventAt'):
                    raise ValueError('Market availability must use the already frozen forecast/event timestamps')
                if any(identity.get(k)!=row.get(v) for k,v in [('sport','sport'),('eventId','gameId'),('playerId','player'),('teamId','team'),('stat','stat')]):
                    raise ValueError('Market mapping differs from the forecast entity')
                prob=threshold_probability(self._draws[i],identity['threshold'],identity['side'],equality=identity['equality'])
                # Sportsbook refund-on-push valuation uses conditional non-push p.
                p=prob['nonPushProbability'] if identity['equality']=='push' else prob['rawProbability']
                if p is None:rows.append({'status':'all_outcomes_push','clvProbabilityPoints':None});continue
                rows.append(compare_market(p,m.get('opening'),identity,cutoff=m['forecastAt'],closing=m.get('closing'),event_at=m.get('eventAt')))
            market={'status':'partial_verified_market_research','observations':sum(r is not None and r.get('marketObservations',0)>0 for r in rows),
                    'rows':rows,'clv':None,'returnDistribution':None,'blendWeight':None,'marketEdgeModel':None}
        result={m.value:stamp_mode(m,self.snapshot_hash,self.model_version,pred) for m,pred in [
            (AccuracyMode.PROBABILITY,probability),(AccuracyMode.NUMERICAL,numerical),(AccuracyMode.MARKET,market)]}
        for r in result.values():r.update(eventSetHash=self.event_hash,eventCount=len({(i['sport'],i['gameId']) for i in self.identities}),
                                         observationCount=len(self.keys),evidenceTier=self.scope,jointRealizations=self.joint,
                                         independentlyValidatedAccuracyClaim=False)
        return result
