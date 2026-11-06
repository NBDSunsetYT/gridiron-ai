"""One explicit, local/background-worker claim. Never called by a UI read."""
import time,signal,threading
from ..reconstruction_v19.runtime import local_only
def run_once(outbox,compute,*,maximum_trials=10000,maximum_seconds=60):
    local_only();job=outbox.claim(lease_seconds=maximum_seconds+5)
    if job is None:return {'status':'idle','simulationsExecuted':0}
    start=time.monotonic()
    if threading.current_thread() is not threading.main_thread():raise ValueError('Run the bounded worker in its own process, never a web request thread')
    previous_handler=signal.getsignal(signal.SIGALRM);previous_timer=signal.getitimer(signal.ITIMER_REAL)
    def deadline(sig,frame):raise TimeoutError('Live worker deadline exceeded')
    signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,min(maximum_seconds,previous_timer[0]) if previous_timer[0]>0 else maximum_seconds)
    try:
        if job['payload']['trials']>maximum_trials:raise ValueError('Per-job simulation budget exceeded')
        result=compute(job['payload'])
        if time.monotonic()-start>maximum_seconds:raise TimeoutError('Result exceeded job deadline; not published')
        outbox.finish(job['id'],job['token'],result=result);return {'status':'complete','id':job['id']}
    except Exception as e:
        try:outbox.finish(job['id'],job['token'],error=type(e).__name__+': '+str(e))
        except ValueError:pass # A newer snapshot fenced this obsolete result.
        return {'status':'withheld','reason':str(e),'id':job['id']}
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous_handler)
        if previous_timer[0]>0:signal.setitimer(signal.ITIMER_REAL,max(.001,previous_timer[0]-(time.monotonic()-start)),previous_timer[1])
