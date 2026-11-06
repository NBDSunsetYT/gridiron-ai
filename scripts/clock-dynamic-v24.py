"""Observed engineering-session heartbeat; never claims inactive execution."""
import sys,time,signal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import Campaign
from modeling.reconstruction_v19.runtime import local_only
local_only();c=Campaign(ROOT/'artifacts/dynamic-v24/runtime');stop=False
def end(sig,frame):
    global stop
    stop=True
signal.signal(signal.SIGTERM,end)
with c.lease():
    c.begin()
    try:
        while not stop and c.may_start(0)[0]:c.heartbeat();time.sleep(5)
    finally:c.end('engineering_checkpoint')
