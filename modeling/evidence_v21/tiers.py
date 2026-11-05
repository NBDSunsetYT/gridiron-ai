"""Add research tiers without lowering the V20 production standard."""
from ..accuracy_v20.quality import assess,aware
def classify(sport,event,cutoff,components,player=None,model_uncertainty=None,consistency=None):
    q=assess(sport,event,cutoff,components,player,model_uncertainty=model_uncertainty)
    consistency=consistency or {};bad=[k for k,v in consistency.items() if v is not True]
    q['consistencyFailures']=bad;q['productionPromotion']=False
    if bad or not q['conditionalResearchAllowed']:
        q.update(tier='blocked',fullGameSimulationAllowed=False,conditionalComponentDiagnosticsAllowed=False)
    elif q['missingDomains'] or q['warnings']:
        q.update(tier='conditional_diagnostic',fullGameSimulationAllowed=False,conditionalComponentDiagnosticsAllowed=True)
    else:q.update(tier='strict_pregame',fullGameSimulationAllowed=True,conditionalComponentDiagnosticsAllowed=True)
    q['promotionStandard']='Unchanged V20 requirements; publication coverage, model uncertainty and independent validation remain mandatory.'
    return q
def timestamped_fact(source,version,published,retrieved,cutoff,modified=None,capture=None):
    if not source.startswith('https://') or not version:raise ValueError('Versioned primary source required')
    pub=aware(published);retr=aware(retrieved);cut=aware(cutoff);mod=aware(modified) if modified else pub
    if max(pub,mod)>=cut or pub>retr:raise ValueError('Source published or modified after cutoff')
    if capture and not pub<=aware(capture)<cut:raise ValueError('Invalid independent pregame capture')
    return {'source':source,'sourceVersion':version,'publishedAt':pub.isoformat(),'modifiedAt':mod.isoformat(),'retrievedAt':retr.isoformat(),'availableAt':max(pub,mod).isoformat(),'independentCaptureAt':capture,'timestampClass':'independently_captured_pregame' if capture else 'publisher_dated_pregame','unknownIsHealthy':False}
