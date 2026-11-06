"""Research-only objective routing over the EXISTING V24 registry.

No second model registry, hardcoded family winner, model fitting, simulation or
production route is introduced. Conditional research wins cannot authorize a
strict forecast. Accuracy modes A/B/C do not replace V23 evidence modes.
"""
from copy import deepcopy
from pathlib import Path
import math
from .accuracy_v20.quality import aware
from .accuracy_v25.objectives import AccuracyMode, objective
from .accuracy_v25.leakage import forecast_lineage_guard
from .dynamic_v24.completion.selection import decision as registry_decision
from .dynamic_v24.registry import FOOTBALL, NBA
from .overnight_v20.state import digest, read

VERSION = 'objective-router-25.2'


def request_guard(request):
    if request.get('sport') not in ('NFL', 'CFB', 'NBA'):
        raise ValueError('Unsupported league')
    if request.get('stat') not in (NBA if request['sport']=='NBA' else FOOTBALL):
        raise ValueError('Statistic is not in the existing league catalogue')
    for key in ('eventId', 'entityId', 'teamId'):
        if not isinstance(request.get(key),str) or not request[key]:
            raise ValueError('Stable event, entity and team IDs required')
    if request.get('entityType') not in ('player','team','game'):
        raise ValueError('Explicit player, team or game identity required')
    if aware(request['cutoff']) > aware(request['eventAt']):
        raise ValueError('Pregame request cutoff cannot follow event start')
    mode = objective(request['output'])
    if request['output']=='quantile' and not 0<float(request.get('quantile',0))<1:
        raise ValueError('Explicit quantile in (0,1) required')
    if mode in (AccuracyMode.PROBABILITY, AccuracyMode.MARKET) and request['stat'] not in ('moneyline','doubleDouble','tripleDouble'):
        if isinstance(request.get('threshold'),bool) or not isinstance(request.get('threshold'),(int,float)) or not math.isfinite(request['threshold']):
            raise ValueError('Exact verified threshold required; no threshold imputation')
        if request.get('side') not in ('over','under') or request.get('equality') not in ('push','win','lose'):
            raise ValueError('Explicit side and settlement equality required')
        if not request.get('thresholdSourceVersion'):
            raise ValueError('Versioned threshold provenance required')
    return mode


def _purposes(request, mode):
    if mode == AccuracyMode.PROBABILITY: return ('distribution',)
    if mode == AccuracyMode.MARKET: return ('market_relative',)
    return ('median',) if request['output'] in ('median','quantile') else ('expected_value',)


def _identity_inputs(request, evidence):
    rows=evidence.get('features',[])
    if not rows: raise ValueError('No input features')
    for r in rows:
        expected_player=request['entityId'] if request['entityType']=='player' else '__team__'
        if r.get('sport')!=request['sport'] or r.get('stat')!=request['stat'] or r.get('team')!=request['teamId'] or r.get('player')!=expected_player:
            raise ValueError('Input player/team/stat/league differs from request')
    if evidence.get('inputSnapshotHash') != digest({'features':rows,'facts':evidence.get('facts',[])}):
        raise ValueError('Input snapshot checksum mismatch')


def _validation_guard(record, attestation, request, protected_ids):
    """A routing attestation references immutable existing records; never edits them."""
    if attestation.get('sha256') != digest({k:v for k,v in attestation.items() if k!='sha256'}):
        raise ValueError('Routing evidence checksum mismatch')
    if attestation.get('registryRecordId') != record['id'] or attestation.get('modelVersion') != record['modelVersion']:
        raise ValueError('Routing validation is not bound to this registry model')
    hashes=record['modelSHA256'] if isinstance(record['modelSHA256'],list) else [record['modelSHA256']]
    if attestation.get('artifactSHA256') not in hashes:
        raise ValueError('Requested artifact is not in the registry record')
    if attestation.get('sourceVersions') != record['sourceVersions']:
        raise ValueError('Source edition mismatch')
    if attestation.get('strictPregameEvidence') is not True:
        raise ValueError('Conditional diagnostics cannot authorize strict routes')
    if attestation.get('productionReferenceCompared') is not True:
        raise ValueError('Reproducible production reference comparison missing')
    cutoff=aware(request['cutoff']);seen=set();previous=None;windows=attestation.get('windows',[])
    if len(windows)<2 or len(windows)!=len(record['metrics']):
        raise ValueError('Two separately verified chronological validation windows required')
    fit_times=record['trainingCutoff'] if isinstance(record['trainingCutoff'],list) else [record['trainingCutoff']]
    if len(fit_times)!=len(windows):
        raise ValueError('Each chronological artifact needs its own training cutoff')
    for window, measured, fitted in zip(windows,record['metrics'],fit_times):
        ids=window.get('gameIds',[]);start=aware(window['start']);end=aware(window['end'])
        if aware(fitted)>=start or start>end or end>=cutoff or (previous is not None and start<=previous):
            raise ValueError('Future, overlapping or unordered validation window')
        if len(ids)!=len(set(ids)) or len(ids)<30 or len(ids)!=measured['games'] or seen.intersection(ids) or set(ids)&protected_ids:
            raise ValueError('Inadequate, protected or repeated validation games')
        if window.get('metricsHash')!=digest(measured) or window.get('gameManifestHash')!=digest(ids):
            raise ValueError('Validation metrics/game manifest mismatch')
        seen.update(ids);previous=end
    if request['eventId'] in seen:
        raise ValueError('Requested game already used in route validation')
    if attestation.get('policyFrozenBeforeValidation') is not True:
        raise ValueError('Selection policy was not frozen before validation')
    # The approved certificate must enumerate the actual artifact's fit,
    # residual-calibration and selection cutoffs, not merely the event date.
    times=attestation.get('artifactAvailableTimes',[])
    if not times or any(aware(t)>=cutoff for t in times):
        raise ValueError('Artifact fit/calibration/selection must precede forecast')
    return digest([{'ids':w['gameIds'],'start':w['start'],'end':w['end']} for w in windows])


class ResearchRouter:
    def __init__(self, registry, *, protected_ids=None):
        self.registry=deepcopy(read(registry) if isinstance(registry,(str,Path)) else registry)
        if protected_ids is None:
            from .integration_v22.datasets import protected
            protected_ids=protected()
        self.protected_ids=set(protected_ids);self.records=self.registry.get('versions',[])
        ids=set()
        for r in self.records:
            if r.get('id')!=digest({k:v for k,v in r.items() if k!='id'}) or r['id'] in ids:
                raise ValueError('Existing registry checksum/identity mismatch')
            ids.add(r['id'])

    def route(self, request, *, evidence=None, attestations=None, qualification=None):
        mode=request_guard(request);rejected=[];eligible=[];evidence=evidence or {};attestations=attestations or {}
        result={'routerVersion':VERSION,'accuracyMode':mode.value,'requestHash':digest(request),
                'status':'withheld','selected':None,'prediction':None,'productionEligible':False,
                'researchOnly':True,'rejected':rejected}
        if request['eventId'] in self.protected_ids:
            return result|{'reason':'protected_event_no_automatic_final_test_access'}
        candidates=[r for r in self.records if r['sport']==request['sport'] and r['stat']==request['stat'] and r['purpose'] in _purposes(request,mode)]
        for r in candidates:
            try:
                if r.get('productionPromotion') is not False:
                    raise ValueError('Research routing cannot modify production approvals')
                review=registry_decision(r['metrics'],r['purpose'],strict=r['decision']['strictPregameEvidence'],production_reference=r['decision']['productionReferenceCompared'])
                if review!=r['decision'] or not review['conditionalImprovementEstablished']:
                    raise ValueError('Candidate failed existing independent registry decision')
                if not review['strictPregameEvidence']:
                    raise ValueError('Only conditional evidence; pregame publication/availability unverified')
                if mode==AccuracyMode.NUMERICAL and request['output']=='mean' and r['estimand']!='conditional_mean':
                    raise ValueError('Median/probability head cannot answer a mean request')
                if request['output']=='quantile':
                    raise ValueError('Validated requested-quantile head unavailable; median is not an arbitrary quantile')
                times=r['trainingCutoff'] if isinstance(r['trainingCutoff'],list) else [r['trainingCutoff']]
                if any(aware(t)>=aware(request['cutoff']) for t in times):
                    raise ValueError('Future fit/selection cutoff')
                a=attestations.get(r['id'],{})
                cohort=_validation_guard(r,a,request,self.protected_ids)
                if mode == AccuracyMode.PROBABILITY:
                    p=a.get('probabilityValidation',{})
                    definition={k:request.get(k) for k in ('sport','stat','threshold','side','equality')}
                    if p.get('definitionHash')!=digest(definition) or p.get('calibrationAccepted') is not True or not p.get('reportSHA256') or p.get('rawAndCalibratedSeparate') is not True:
                        raise ValueError('Exact outcome probability/calibration validation missing; CDF diagnostics are insufficient')
                if mode == AccuracyMode.MARKET:
                    raise ValueError('No independently validated market-relative head schema; retain Mode C research-only evidence evaluation')
                _identity_inputs(request,evidence)
                if any(f.get('sport')!=request['sport'] for f in evidence.get('facts',[])):
                    raise ValueError('Source evidence league mismatch')
                if not all(any(f.get('teamId')==request['teamId'] for f in evidence.get('facts',[]) if f['kind']==kind) for kind in ('injury','lineup','participation')):
                    raise ValueError('Exact requested team availability coverage missing')
                forecast_lineage_guard(evidence['features'],evidence.get('facts',[]),request['cutoff'],request['eventId'],max(times,key=aware))
                for kind in ('injury','lineup','participation','historical_statistics'):
                    facts=[f for f in evidence['facts'] if f['kind']==kind]
                    limit=a.get('freshnessSeconds',{}).get(kind)
                    if isinstance(limit,bool) or not isinstance(limit,(int,float)) or not math.isfinite(limit) or limit<=0 or not facts:
                        raise ValueError('Validated freshness policy missing: '+kind)
                    if any((aware(request['cutoff'])-aware(f['availableAt'])).total_seconds()>limit for f in facts):
                        raise ValueError('Stale '+kind+' evidence')
                if not qualification:
                    raise ValueError('Model-bound joint simulation qualification missing')
                from .fullgame_v23.forecast import require
                from .dynamic_v24.completion.selection import joint_probability_gate
                require(**qualification)
                joint_probability_gate(qualification['model'],qualification['match'],qualification['certificate'])
                model=qualification['model'];match=qualification['match'];cert=qualification['certificate']
                if model.get('sport')!=request['sport'] or match['id']!=request['eventId'] or aware(match['cutoff'])!=aware(request['cutoff']):
                    raise ValueError('Joint qualification event/league/cutoff mismatch')
                bound=cert.get('objectiveHeadValidation',{}).get(r['id'],{})
                if r['id'] not in model.get('specializedHeadIds',[]) or bound.get('artifactSHA256')!=a['artifactSHA256'] or bound.get('inputSnapshotHash')!=evidence['inputSnapshotHash'] or bound.get('compatible') is not True:
                    raise ValueError('Selected head not certified against this shared game distribution')
                eligible.append((r,a,cohort))
            except (ValueError,KeyError,TypeError) as error:
                rejected.append({'id':r['id'],'family':r['family'],'reason':str(error)})
        if not eligible:
            return result|{'reason':'no_independently_eligible_objective_model','candidateCount':len(candidates)}
        if len({v[2] for v in eligible})!=1:
            return result|{'reason':'eligible_models_have_incomparable_validation_cohorts'}
        metric=('brier' if request['stat'] in ('moneyline','doubleDouble','tripleDouble') else 'crps') if mode==AccuracyMode.PROBABILITY else ('mae' if request['output']=='median' else 'rmse')
        def score(item):
            windows=item[0]['metrics'];return sum(w['candidate'][metric]*w['games'] for w in windows)/sum(w['games'] for w in windows)
        ranked=sorted(eligible,key=lambda item:(score(item),item[0]['id']))
        if len(ranked)>1:
            # Do not declare a winner by sorting noisy retrospective point scores.
            selection=ranked[0][1].get('pairedSelection',{})
            if selection.get('against')!=sorted(r[0]['id'] for r in ranked[1:]) or selection.get('adjustedUpperBound',0)>=0 or selection.get('metric')!=metric or selection.get('cohortHash')!=ranked[0][2]:
                return result|{'reason':'head_to_head_selection_uncertainty_unresolved'}
        r,a,cohort=ranked[0]
        return result|{'status':'eligible_research_route','reason':'independently_validated_objective_and_joint_binding',
                       'selected':{'registryRecordId':r['id'],'modelVersion':r['modelVersion'],
                                   'artifactSHA256':a['artifactSHA256'],'family':r['family'],'purpose':r['purpose'],
                                   'trainingCutoff':r['trainingCutoff'],'validationCohortHash':cohort,
                                   'uncertainty':r['uncertainty'],'calibrated':a.get('calibratorValidated') is True,
                                   'inputSnapshotHash':evidence['inputSnapshotHash'],
                                   'jointModelHash':qualification['model']['sha256']}}

    def predict(self,request,*,cached_forecast=None,**kwargs):
        """Retrieve a qualified cached head output. Never simulate in a request."""
        route=self.route(request,**kwargs)
        if route['status']!='eligible_research_route': return route
        cached=cached_forecast or {};selected=route['selected']
        if cached.get('sha256')!=digest({k:v for k,v in cached.items() if k!='sha256'}):
            return route|{'status':'withheld','reason':'cached_prediction_checksum_missing_or_invalid'}
        for key,expected in [('requestHash',digest(request)),('registryRecordId',selected['registryRecordId']),
                             ('artifactSHA256',selected['artifactSHA256']),('inputSnapshotHash',selected['inputSnapshotHash']),
                             ('jointModelHash',selected['jointModelHash'])]:
            if cached.get(key)!=expected:
                return route|{'status':'withheld','reason':'cached_prediction_binding_mismatch:'+key}
        if aware(cached['createdAt'])>aware(request['cutoff']) or cached.get('stale') is not False:
            return route|{'status':'withheld','reason':'cached_prediction_stale_or_post_cutoff'}
        if cached.get('accuracyMode')!=route['accuracyMode'] or cached.get('prediction') is None:
            return route|{'status':'withheld','reason':'cached_objective_output_missing_or_mismatched'}
        return route|{'status':'ready_research_only','prediction':cached['prediction'],
                      'predictionHash':cached['sha256'],'lastVerifiedAt':cached.get('lastVerifiedAt')}
