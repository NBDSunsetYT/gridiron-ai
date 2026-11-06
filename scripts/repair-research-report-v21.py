"""Grade a value already frozen before outcomes; never refit or rewrite it."""
import sys,json,gzip
from pathlib import Path
from importlib.machinery import SourceFileLoader
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.evidence_v21.runtime import job
from modeling.evidence_v21.io import OUT
from modeling.evidence_v21.forecast_schema import nested_predictions
from modeling.overnight_v20.state import atomic
from modeling.iterative_learning import freeze_json
def run():
    folder=OUT/'source-repair/NBA';rows=json.loads(gzip.decompress((folder/'grades.json.gz').read_bytes()));snapshot=json.loads(gzip.decompress((folder/'forecasts.json.gz').read_bytes()));saved=sum('lineup_state_minutes' in r for r in snapshot['rows']);fixed=[nested_predictions(r) for r in rows];metrics=SourceFileLoader('v21_fixed_metrics',str(ROOT/'scripts/research-independent-v21.py')).load_module();rr=[r for r in fixed if r['stat']=='minutes'];result={'reason':'The starter-state prediction was frozen at the record top level instead of inside predictions. Grade its original pre-outcome value through a versioned schema adapter.','refits':0,'originalForecastsRewritten':False,'alreadyFrozenStateValues':saved,'games':len({r['gameId'] for r in rr}),'minutes':{ref:metrics.paired(rr,'lineup_state_minutes',ref) for ref in ['raw_hurdle','raw_rolling5']},'productionPromotion':False,'strictQualifiedGames':0};freeze_json(folder/'schema-r2-grades.json.gz',fixed);atomic(folder/'schema-r2-results.json',result);return {'gradedGames':result['games'],'alreadyFrozenStateValues':saved,'refits':0,'originalForecastsChanged':False}
if __name__=='__main__':print(json.dumps(job('forecast-report-schema',run,cpu=120,wall=300,revision='schema-r2'),indent=2))
