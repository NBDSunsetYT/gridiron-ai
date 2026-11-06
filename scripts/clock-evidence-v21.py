"""Observed local research accounting; never writes V20's ledger."""
import sys,time,signal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import Campaign
from modeling.reconstruction_v19.runtime import local_only
local_only();c=Campaign(ROOT/'artifacts/overnight-v21/runtime');stop=False
def end(sig,frame):
    global stop
    stop=True
signal.signal(signal.SIGTERM,end);signal.signal(signal.SIGINT,end)
with c.lease():
    c.begin()
    try:
        while not stop:
            if not c.may_start(0)[0]:break
            c.heartbeat();time.sleep(5)
    finally:c.end('v21_evidence_implementation_checkpoint')
