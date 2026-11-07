"""Transparent point-in-time evidence coverage, never a probability of accuracy."""
from datetime import datetime,timezone
import math

VERSION='pit-evidence-policy-20.2'
DOMAINS=('identity','historical_statistics','injury','lineup','participation')
def aware(v):
    if not v:raise ValueError('An explicit timezone-aware timestamp is required')
    d=datetime.fromisoformat(str(v).replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('Timestamp timezone missing')
    return d.astimezone(timezone.utc)
def assess(sport,event_id,cutoff,components,player_id=None,model_uncertainty=None,mc_se=None,maximum_model_probability_width=.5):
    if sport not in ('NFL','CFB','NBA'):raise ValueError('Separate supported league required')
    when=aware(cutoff);required=(*DOMAINS,*(('weather',) if sport!='NBA' else ()));audited={};missing=[];verified=[];warnings=[]
    for domain in required:
        r=dict(components.get(domain) or {});classification=r.get('classification','unavailable');reason=None
        if classification not in ('confirmed','projected','inferred','unavailable'):raise ValueError('Invalid evidence classification')
        if r.get('eventId') not in (None,event_id):reason='event_identity_mismatch'
        if player_id and r.get('playerId') not in (None,player_id):reason='player_identity_mismatch'
        if not reason and r.get('publishedAt'):
            try:
                if aware(r['publishedAt'])>=when:reason='published_after_prediction_cutoff'
                if r.get('retrievedAt') and aware(r['retrievedAt'])<aware(r['publishedAt']):reason='retrieval_precedes_publication'
            except ValueError:reason='invalid_source_timestamp'
        # A source's original date cannot qualify a later corrected edition.
        # Prospective receipts prove availability only before, not at, cutoff.
        if not reason:
            try:
                if any(aware(r[k])>=when for k in ('modifiedAt','dateModified','availableAt') if r.get(k)):
                    reason='source_edition_not_before_prediction_cutoff'
            except ValueError:reason='invalid_source_timestamp'
        established_by=r.get('publishedAt')
        if not reason and not established_by:
            # An immutable receipt captured before cutoff proves availability
            # without inventing a publisher's original publication timestamp.
            if r.get('retrievedAt') and r.get('immutableReceipt') is True and r.get('sourceVersion'):
                try:
                    if aware(r['retrievedAt'])<when:established_by=r['retrievedAt']
                except ValueError:reason='invalid_source_timestamp'
            if not established_by and not reason:reason='original_publication_or_pre_cutoff_receipt_unverified'
        if not reason and (not str(r.get('source','')).startswith('https://') or not r.get('sourceVersion')):reason='source_or_version_unverified'
        if not reason and classification not in ('confirmed','projected'):reason='evidence_not_verified'
        if not reason and r.get('complete') is not True:reason='partial_evidence'
        ok=reason is None
        audited[domain]={**r,'classification':classification,'eligibleBeforeCutoff':ok,'availabilityEstablishedBy':established_by,'failure':reason}
        (verified if ok else missing).append(domain)
        if ok and classification=='projected':warnings.append(domain+':projected_not_confirmed')
    quantified=False;excessive=False
    if isinstance(model_uncertainty,dict) and model_uncertainty.get('validated') is True and model_uncertainty.get('sourceVersion'):
        bounds=model_uncertainty.get('probabilityInterval95',[])
        quantified=len(bounds)==2 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in bounds) and 0<=bounds[0]<=bounds[1]<=1
        if quantified:excessive=bounds[1]-bounds[0]>maximum_model_probability_width
    if not quantified:warnings.append('model_uncertainty_not_quantified')
    if excessive:warnings.append('model_uncertainty_exceeds_predeclared_width_policy')
    if mc_se is not None and (not math.isfinite(mc_se) or mc_se<0):raise ValueError('Invalid Monte Carlo error')
    if mc_se is not None and mc_se>.01:warnings.append('monte_carlo_precision_target_not_met')
    withheld=bool(missing or not quantified or excessive or 'lineup:projected_not_confirmed' in warnings)
    return {'policyVersion':VERSION,'sport':sport,'eventId':event_id,'playerId':player_id,'predictionCutoff':when.isoformat(),'pointInTimeEvidenceScore':round(100*len(verified)/len(required),2),'scoreMeaning':'Equal-weight percentage of required domains with complete, source-versioned evidence published by cutoff. Coverage policy, not accuracy or availability probability.','verifiedDomains':verified,'missingDomains':missing,'components':audited,'warnings':warnings,'decision':'withhold_unconditional_forecast' if withheld else 'evidence_checks_passed_model_validation_still_required','conditionalResearchAllowed':not any(v['failure'] in ('event_identity_mismatch','player_identity_mismatch','published_after_prediction_cutoff','invalid_source_timestamp','retrieval_precedes_publication') for v in audited.values()),'missingMeansHealthy':False,'productionPromotion':False}
