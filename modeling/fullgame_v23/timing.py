"""Observed action-clock laws and independent gamebook interval diagnostics."""
import re
from .ordering import canonical_order,seconds
def nba_action_intervals(events):
    previous={};values=[];administrative=0
    for r in canonical_order(events):
        q=int(r['period_number']);clock=seconds(r);typ=str(r.get('type_text','')).lower();text=str(r.get('text','')).lower();first_ft=bool(re.search(r'free throw 1 of [123]',text)) and 'technical' not in text
        action=bool(r.get('shooting_play')) and 'free throw' not in text or 'turnover' in typ or typ in ('traveling','double dribble','palming') or first_ft
        if not action:administrative+=1;continue
        last=previous.get(q,720 if q<=4 else 300);delta=last-clock
        if delta<0:raise ValueError('Action clock moved backward')
        if delta>0:values.append(delta)
        previous[q]=clock
    if len(values)<100:raise ValueError('One hundred observed positive offensive-action intervals required')
    return values,{'observedPositiveActionIntervals':len(values),'administrativeRowsNotTreatedAsPossessions':administrative,'physicalSnapTimesClaimed':False,'shotClockCapsAppliedByEngine':True}
