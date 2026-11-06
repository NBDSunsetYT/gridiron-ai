"""One qualified existing full-game run, reused across objective requests.

Explicit local batch entry point. This does not register an API route, automatic
refresh hook, new worker or production model. Existing scientific gates run
before consulting the content-addressed, process-locked aggregate cache.
"""
from pathlib import Path
import fcntl
import math
import signal,time,threading
from contextlib import contextmanager
from ..overnight_v20.state import digest,read
from ..iterative_learning import freeze_json
from ..reconstruction_v19.runtime import local_only
from ..dynamic_v24.completion.joint import forecast_with_heads


@contextmanager
def bounded_call(cpu_seconds,wall_seconds):
    if threading.current_thread() is not threading.main_thread() or not 0<cpu_seconds<=180 or not 0<wall_seconds<=360:
        raise ValueError('Explicit bounded local main-thread worker required; maximum 180 CPU / 360 wall seconds')
    saved=[];start=time.monotonic();cpu=time.process_time()
    def stop(signum,frame):raise TimeoutError('Shared research job exhausted its compute budget; no partial forecast cached')
    try:
        for timer,sig,limit in [(signal.ITIMER_REAL,signal.SIGALRM,wall_seconds),(signal.ITIMER_PROF,signal.SIGPROF,cpu_seconds)]:
            old=signal.getitimer(timer);handler=signal.getsignal(sig);saved.append((timer,sig,old,handler))
            signal.signal(sig,stop);signal.setitimer(timer,min(limit,old[0]) if old[0]>0 else limit)
        yield
    finally:
        for timer,sig,old,handler in reversed(saved):
            signal.setitimer(timer,0);signal.signal(sig,handler)
            used=time.monotonic()-start if timer==signal.ITIMER_REAL else time.process_time()-cpu
            signal.setitimer(timer,max(1e-6,old[0]-used) if old[0]>0 else 0,old[1])


def run_once(registry,qualification,cache_folder,*,kernel=None,seed=250025,conversions=None,cpu_seconds=180,wall_seconds=360):
    local_only()
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<2**32:
        raise ValueError('Reproducible unsigned 32-bit integer seed required')
    from ..fullgame_v23.forecast import require
    from ..dynamic_v24.completion.selection import joint_probability_gate
    require(**qualification)
    model=qualification['model'];match=qualification['match'];ctx=qualification['ctx']
    joint_probability_gate(model,match,qualification['certificate'])
    if model.get('sport')!=ctx.get('sport') or ctx.get('eventId')!=match['id']:
        raise ValueError('Shared game identity mismatch')
    # Fail all head/certificate gates before even creating a cache directory.
    registry.joint_heads(model['sport'],**qualification)
    identity={'modelHash':model['sha256'],'eventId':match['id'],'cutoff':match['cutoff'],
              'sport':model['sport'],'kernelInputHash':model.get('kernelInputHash'),
              'evidenceHash':digest(qualification['evidence']),'contextHash':digest(ctx),
              'conversionsHash':digest(conversions),'seed':seed,'games':10000}
    key=digest(identity);folder=Path(cache_folder);folder.mkdir(parents=True,exist_ok=True)
    target=folder/(key+'.json')
    with (folder/(key+'.lock')).open('a') as lease:
        try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Shared simulation already running; no duplicate computation started')
        cached=read(target)
        if cached is not None:
            if cached.get('sha256')!=digest({k:v for k,v in cached.items() if k!='sha256'}) or cached.get('identity')!=identity:
                raise ValueError('Cached shared-game result failed integrity validation')
            return cached|{'cacheHit':True}
        with bounded_call(cpu_seconds,wall_seconds):
            result=forecast_with_heads(registry,**qualification,kernel=kernel,games=10000,seed=seed,conversions=conversions)
        if result.get('games')!=10000 or result.get('mechanicalInvariantsPassed') is not True or result.get('researchContext')!=ctx:
            raise ValueError('Existing engine did not return a complete mechanically verified qualified run')
        if result.get('allSimulatedPlaysPermanentlyStored') is not False or 'results' in result:
            raise ValueError('Only compact aggregate simulations may be cached')
        if len(result.get('scoreDistributions',{}))!=2 or len(result.get('representativeGames',[]))>3:
            raise ValueError('Two teams and at most three representative games required')
        distributions=[*result.get('scoreDistributions',{}).values(),result.get('totalDistribution',{}),result.get('marginDistribution',{})]
        distributions.extend(v for stats in result.get('playerDistributions',{}).values() for v in stats.values())
        for distribution in distributions:
            hist=distribution.get('histogram',[])
            if not hist or any(isinstance(r['count'],bool) or not isinstance(r['count'],int) or r['count']<0 or not math.isfinite(r['value']) for r in hist) or sum(r['count'] for r in hist)!=10000:
                raise ValueError('Shared score distribution does not contain exactly 10,000 valid games')
        envelope={'identity':identity,'sharedSimulationId':key,'result':result,
                  'marginPositiveTeam':next(iter(result['scoreDistributions'])),
                  'accuracyModes':['A_probability','B_numerical','C_market_research'],
                  'oneSimulationForAllObjectives':True,'productionEligible':False}
        envelope|={'sha256':digest(envelope)};freeze_json(target,envelope)
        return envelope|{'cacheHit':False}
