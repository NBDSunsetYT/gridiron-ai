"""Legal live/running/stopped clock phases with source-backed latent timing.

Printed snap/end pairs identify some live durations. Other plays borrow a
documented same-league prior, never a made-up physical timestamp. Mechanical
replay keeps uncertain historical intervals uncertain; this law is for draws.
"""
import re
from collections import defaultdict
from .replay import clock_seconds
class PhaseClockLaw:
    def __init__(self,observations,sport):
        valid=[r for r in observations if r['sport']==sport and 0<r['seconds']<=90 and r.get('sourceVersion')]
        if not valid:raise ValueError('Verified same-league live-clock observations required')
        self.sport=sport;self.observations=valid;self.pools=defaultdict(list)
        for r in valid:self.pools[r['kind']].append(r['seconds'])
        self.prior=[r['seconds'] for r in valid];self.borrowed=0;self.stops=defaultdict(int)
    def advance(self,rng,clock,kind,complete,total_charge,*,first_down=False,out_of_bounds=False,terminal=False,explicit_runoff=None):
        if clock.period in (2,4) and (clock.sport=='NFL' or clock.season>=2024) and not clock.warning_taken and clock.remaining==120:
            clock.pending_warning=True;clock.take_warning();clock.running=False;self.stops['two_minute_timeout']+=1
        if kind=='penalty':
            # No-play action does not imply zero elapsed game clock. A
            # running clock can burn time before the flag; a stopped one
            # cannot. Explicit ten-second elections are a separate phase.
            if clock.running:
                self._running(clock,min(total_charge,40));self.stops['administrative_running_phase']+=1
            clock.running=False
            if explicit_runoff is not None:
                amount=clock.runoff('foul',True)
                if amount!=explicit_runoff:raise ValueError('Runoff annotation contradicts timing/election rules')
            return
        pool=self.pools.get(kind)
        if not pool:self.borrowed+=1;pool=self.prior
        live=float(rng.choice(pool));clock.advance(min(live,clock.remaining));warning=clock.pending_warning
        if warning:clock.take_warning();self.stops['two_minute_timeout']+=1
        if first_down and clock.sport=='CFB':
            rule=clock.first_down_rule()
            if rule['automaticFirstDownStop']:self.stops['first_down_ready_for_play_stop']+=1
        last_half=clock.period in (2,4)
        oob_snap=out_of_bounds and last_half and clock.remaining<=(300 if clock.sport=='NFL' and clock.period==4 else 120)
        stop=(kind in ('pass','spike') and not complete) or terminal or warning or oob_snap
        clock.running=not stop
        if stop:self.stops['restart_on_snap']+=1
        else:self._running(clock,min(40,max(0,total_charge-live)))
    def _running(self,clock,charge):
        charge=min(charge,clock.remaining)
        warning_due=clock.period in (2,4) and (clock.sport=='NFL' or clock.season>=2024) and not clock.warning_taken and clock.remaining>120 and clock.remaining-charge<=120
        if warning_due:
            clock.advance(clock.remaining-120,kind='running');clock.take_warning();clock.running=False;self.stops['two_minute_timeout']+=1
        elif charge:clock.advance(charge,kind='running')
    def diagnostics(self):return {'livePairs':len(self.observations),'sameLeaguePriorBorrowingDraws':self.borrowed,'clockStops':dict(self.stops),'individualHistoricalDurationInvented':False,'parameterUncertaintyValidated':False}

def explicit_cfb_live_pairs(actions,source):
    out=[]
    for r in actions:
        a=r['action'];start=re.match(r'^\((\d+:\d\d)\)',a);end=re.search(r'\bclock\s+(\d+:\d\d)',a,re.I)
        if not start or not end or r['noPlay'] or r['period']>4:continue
        duration=clock_seconds(start[1])-clock_seconds(end[1])
        if 0<duration<=90:out.append({'sport':'CFB','kind':r['kind'],'seconds':duration,'sourceVersion':source['sourceVersion'],'source':source['source'],'statement':r['sourceLine'],'interpretation':'Explicit printed snap/end game-clock pair; not a coarsened same-clock guess'})
    return out

def nfl_stopped_live_pairs(rows,source):
    out=[];rs=sorted(rows,key=lambda r:r['play_id'])
    for i,r in enumerate(rs[:-1]):
        if r.get('no_play') or r.get('penalty') or r.get('qtr',0)>4:continue
        following=rs[i+1]
        if following.get('qtr')!=r.get('qtr') or following.get('penalty'):continue
        # Incompletions, an explicit out-of-bounds dead ball, and scoring
        # plays stop the game clock. Absent an intervening adjustment, the
        # next snap/dead-ball clock fixes the consumed live game-clock time.
        late_oob=r.get('out_of_bounds') and (r.get('qtr')==2 and r['quarter_seconds_remaining']<=120 or r.get('qtr')==4 and r['quarter_seconds_remaining']<=300)
        stop=r.get('incomplete_pass') or late_oob or r.get('touchdown') or r.get('field_goal_attempt')
        if not stop:continue
        duration=float(r['quarter_seconds_remaining'])-float(following['quarter_seconds_remaining'])
        if 0<duration<=90:out.append({'sport':'NFL','kind':'sack' if r.get('sack') else 'pass' if r.get('pass_attempt') else 'rush' if r.get('rush_attempt') else 'field_goal','seconds':duration,'sourceVersion':source['sourceVersion'],'source':source['source'],'playId':r['play_id'],'followingPlayId':following['play_id'],'interpretation':'Stopped-clock adjacent source anchors; original publication/correction history unverified'})
    return out
