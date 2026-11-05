"""Account for the supervised accuracy-first implementation interval."""
import sys,time,signal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import Campaign
c=Campaign(ROOT/'artifacts/overnight-v20/runtime');stop=False
def handle(sig,frame):
    global stop
    stop=True
signal.signal(signal.SIGTERM,handle);signal.signal(signal.SIGINT,handle)
with c.lease():
    c.begin()
    try:
        while not stop:
            s=c.heartbeat()
            if s['measuredActiveSeconds']+s['unobservedActiveUpperBoundSeconds']+s.get('setupSafetyChargeSeconds',0)>=35990:break
            time.sleep(5)
    finally:c.end('accuracy_first_implementation_checkpoint')
