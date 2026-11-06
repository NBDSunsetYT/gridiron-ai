"""Check, never force, a specialized marginal against shared-event outcomes.

These are Monte Carlo consistency diagnostics, NOT historical accuracy or model
uncertainty certificates. All thresholds are frozen before observing outputs.
"""
from statistics import NormalDist
import math
import numpy as np
from ..overnight_v20.state import digest

VERSION='joint-marginal-consistency-25.2'


def compare(record_id,artifact_hash,input_hash,joint_hash,mean,marginal,joint,*,alpha=.01,heads=1):
    a,b=np.asarray(marginal,float),np.asarray(joint,float)
    if not all(isinstance(v,str) and v for v in (record_id,artifact_hash,input_hash,joint_hash)):
        raise ValueError('Stable model, artifact, input and joint identities required')
    if a.ndim!=1 or b.ndim!=1 or min(len(a),len(b))<1000 or not np.isfinite(a).all() or not np.isfinite(b).all() or not math.isfinite(mean):
        raise ValueError('At least 1,000 actual finite realizations from each distribution required')
    if not 0<alpha<=.05 or isinstance(heads,bool) or not isinstance(heads,int) or heads<1:
        raise ValueError('Frozen multiplicity policy required')
    tolerance=math.sqrt(math.log(4*heads/alpha)/(2*len(a)))+math.sqrt(math.log(4*heads/alpha)/(2*len(b)))
    grid=np.unique(np.r_[a,b]);aa=np.sort(a);bb=np.sort(b)
    distance=float(np.max(np.abs(np.searchsorted(aa,grid,side='right')/len(a)-np.searchsorted(bb,grid,side='right')/len(b))))
    se=float(np.std(b,ddof=1)/math.sqrt(len(b)))
    mean_limit=NormalDist().inv_cdf(1-alpha/(2*heads))*se
    mean_error=abs(float(b.mean())-mean)
    roundoff=32*math.ulp(max(1.,abs(mean),abs(float(b.mean()))))
    rare=mean!=0 and (np.count_nonzero(a)<50 or np.count_nonzero(b)<50)
    reasons=[]
    if rare:reasons.append('insufficient_nonzero_support_for_mean_normal_approximation')
    if mean_error>mean_limit+roundoff:reasons.append('mean_incompatible_beyond_monte_carlo_error')
    if distance>tolerance:reasons.append('predictive_distribution_incompatible')
    report={'version':VERSION,'registryRecordId':record_id,'artifactSHA256':artifact_hash,
            'inputSnapshotHash':input_hash,'jointModelHash':joint_hash,'compatible':not reasons,
            'scope':'marginal_MC_consistency_only_not_predictive_validation','reasons':reasons,
            'targetMean':float(mean),'jointMean':float(b.mean()),'meanDifference':mean_error,
            'meanMonteCarloSE':se,'meanLimit':mean_limit,'meanMethod':'Normal approximation; rare support withheld',
            'cdfDistance':distance,'simultaneousDKWLimit':tolerance,'alpha':alpha,'heads':heads,
            'marginalSamples':len(a),'jointSamples':len(b),'marginalDrawHash':digest(a.tolist()),
            'jointDrawHash':digest(b.tolist()),'distributionsModified':False,'productionEligible':False,
            'modelUncertainty':'not_established_by_sampling_precision'}
    return report|{'sha256':digest(report)}


def require_report(report,record_id,artifact_hash,input_hash,joint_hash):
    if not report or report.get('sha256')!=digest({k:v for k,v in report.items() if k!='sha256'}):
        raise ValueError('Joint/marginal consistency report checksum missing or invalid')
    if report.get('version')!=VERSION or report.get('compatible') is not True or report.get('distributionsModified') is not False:
        raise ValueError('Selected marginal has not passed non-forcing compatibility checks')
    expected={'registryRecordId':record_id,'artifactSHA256':artifact_hash,'inputSnapshotHash':input_hash,'jointModelHash':joint_hash}
    if any(report.get(k)!=v for k,v in expected.items()):
        raise ValueError('Compatibility report belongs to another head, artifact, input or joint model')
    return report
