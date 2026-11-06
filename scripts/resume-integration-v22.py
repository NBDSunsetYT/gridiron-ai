"""Explicit immutable revision registration; no changed numerical hypotheses."""
import sys,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.integration_v22.runtime import job
from modeling.integration_v22.io import OUT
from modeling.overnight_v20.state import atomic,read,digest
spec=importlib.util.spec_from_file_location('v22_run',ROOT/'scripts/integration-v22.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
if __name__=='__main__':
    name='components-r2';path=OUT/'specs'/(name+'.json')
    if '--register' in sys.argv:
        if path.exists():raise ValueError('Revision already registered')
        atomic(path,{'name':name,'numericCode':module.code(),'protocolHash':digest(read(OUT/'protocol.json')),'reason':'R1 interrupted before forecasts: production replay redundantly re-read protected manifest per raw record. Hoist invariant protected set once; identical exclusion and model arithmetic. No outcomes graded or parameters changed.'});print('Registered invariant-hoisting repair')
    else:print(job(name,module.components,cpu=1200,wall=2400))
