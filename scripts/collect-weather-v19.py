"""Balanced original-forecast qualification cases; never changes frozen predictions."""
import sys,json,time,hashlib
from pathlib import Path
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.reconstruction_v19.weather import fetch_field_ranges
from modeling.reconstruction_v19.evidence import aware,Evidence
from modeling.iterative_learning import freeze_json
from modeling.reconstruction_v19.runtime import local_only
local_only();out=ROOT/'artifacts/parallel-v19';protocol=json.load((out/'protocol.json').open());results=[];cpu=time.process_time()
# Coarse public stadium coordinates. The archive returns the nearest 0.25-degree
# model grid cell and distance, never claims an on-field sensor observation.
venues={'NFL':('CAR',35.2258,-80.8528,'Bank of America Stadium'),'CFB':('cfb:espn:2628',32.7098,-97.3682,'Amon G. Carter Stadium')}
for sport,(home,lat,lon,name) in venues.items():
    g=protocol['selection'][sport][0]
    if g['home']!=home:raise ValueError('Venue/team identity mapping changed')
    run='2025-10-03T00:00:00Z';lead=int((aware(g['at']).replace(minute=0,second=0,microsecond=0)-aware(run)).total_seconds()/3600);cutoff=(aware(g['at'])-timedelta(hours=1)).isoformat();r=fetch_field_ranges(run,lead,lat,lon,cutoff,out/'sources/gfs-ranges');r.update(sport=sport,eventId=g['id'],venue=name);results.append(r);print(json.dumps({'sport':sport,'event':g['id'],'forecastRun':run,'leadHours':lead,'temperatureCelsius':r['temperatureCelsius'],'windSpeedKph':r['windSpeedKph'],'cpuSeconds':time.process_time()-cpu}),flush=True)
freeze_json(ROOT/'docs/reports/parallel-v19-weather-evidence.json',{'cases':results,'cpuSeconds':time.process_time()-cpu,'forecastsChanged':False,'sourceStage':'Post-freeze data-quality improvement; excluded from the in-flight numerical model comparison.'})
