"""Bounded, payload-free diagnostics. No provider keys, identities or URLs."""
import contextvars
import logging
import os
import resource
import threading
import time
from collections import deque

path_context=contextvars.ContextVar('operation',default='compute')
_lock=threading.Lock();_metrics={};_events={}

def record(path,wall,cpu=0,error=False):
    with _lock:
        if path not in _metrics:
            if len(_metrics)>=64:_metrics.pop(next(iter(_metrics)))
            _metrics[path]={'requests':0,'errors':0,'cpuSeconds':0.,'wallSeconds':0.,'latencies':deque(maxlen=128)}
        m=_metrics[path];m['requests']+=1;m['errors']+=int(error);m['cpuSeconds']+=cpu;m['wallSeconds']+=wall;m['latencies'].append(wall)

def event(name):
    with _lock:_events[name]=_events.get(name,0)+1

def snapshot():
    with _lock:
        return {'scope':'current_process','rssHighWaterBytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                'processCpuSeconds':time.process_time(),'events':dict(_events),
                'operations':{k:{**{a:b for a,b in m.items() if a!='latencies'},'p95Seconds':sorted(m['latencies'])[max(0,__import__('math').ceil(len(m['latencies'])*.95)-1)]} for k,m in _metrics.items()}}

def timed_work(work):
    start=time.perf_counter();cpu=time.thread_time();failed=False
    try:return work()
    except Exception:failed=True;raise
    finally:record(path_context.get()+':work',time.perf_counter()-start,time.thread_time()-cpu,failed)

def install(app):
    @app.middleware('http')
    async def observe(request,call_next):
        path=request.url.path
        # IDs/query strings never enter metric labels. The only dynamic data
        # route has a bounded resource name; collapse unknown routes.
        if len(path)>80 or path.count('/')>4:path='other'
        start=time.perf_counter();ctx=path_context.set(path)
        try:
            response=await call_next(request);record(path,time.perf_counter()-start,error=response.status_code>=500)
            if path!='/health':response.headers['Server-Timing']='app;dur=%.2f'%((time.perf_counter()-start)*1000)
            return response
        finally:path_context.reset(ctx)
