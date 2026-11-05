"""Paired, game-clustered point-forecast comparisons, not calibration claims."""
from collections import defaultdict
import numpy as np
from ..structural_v18.models import error_metrics
def paired(rows,candidate,reference):
    rs=[r for r in rows if candidate in r['predictions'] and reference in r['predictions']]
    if not rs:return None
    grouped=defaultdict(list)
    for r in rs:grouped[r['gameId']].append(abs(r['predictions'][candidate]-r['actual'])-abs(r['predictions'][reference]-r['actual']))
    sums=np.array([[sum(v),len(v)] for _,v in sorted(grouped.items())]);rng=np.random.default_rng(22220);draw=sums[rng.integers(0,len(sums),(2000,len(sums)))].sum(axis=1)
    return {'games':len(grouped),'players':len({r['player'] for r in rs}),'observations':len(rs),'candidate':error_metrics([r['actual'] for r in rs],[r['predictions'][candidate] for r in rs]),'reference':error_metrics([r['actual'] for r in rs],[r['predictions'][reference] for r in rs]),'pairedMAEDelta':float(sums[:,0].sum()/sums[:,1].sum()),'bootstrap95':np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist(),'referenceFamily':reference,'unit':'game-clustered observation MAE','promotionAllowed':False}
