"""Reconcile archived forecast valid time with verified scheduled kickoff.
The first CFB provenance probe followed a midnight PBP placeholder. Retain it as
source research, but do not treat it as kickoff weather. No frozen model changes.
"""
import sys,json,gzip
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.reconstruction_v19.weather import fetch_field_ranges
from modeling.iterative_learning import freeze_json
OUT=ROOT/'artifacts/parallel-v19';target=ROOT/'docs/reports/parallel-v19-weather-alignment.json'
if target.exists():print('Immutable weather alignment already collected');sys.exit(0)
old=json.load((ROOT/'docs/reports/parallel-v19-weather-evidence.json').open());nfl=old['cases'][0];cfb=old['cases'][1]
# Original model cutoff is preserved, while the prediction valid time is chosen
# using the independently reconciled event schedule, not a box-score feature.
box=json.loads(gzip.decompress((OUT/'outcomes/cfb_espn_401756914.official.json.gz').read_bytes()))['box'];scheduled=datetime.fromisoformat(box['scheduledStart'].replace('Z','+00:00'));run=datetime.fromisoformat(cfb['run'].replace('Z','+00:00'));lead=int((scheduled-run).total_seconds()//3600);updated=fetch_field_ranges(cfb['run'],lead,cfb['latitude'],cfb['longitude'],cfb['cutoff'],OUT/'sources/gfs-ranges');updated['eventId']=cfb['eventId'];updated['scheduledStart']=box['scheduledStart'];valid=datetime.fromisoformat(updated['fields'][0]['forecastValidAt']);updated['validOffsetMinutesFromKickoff']=(valid-scheduled).total_seconds()/60;updated['confidence']='provider_snapshot_original_operational_forecast'
if abs(updated['validOffsetMinutesFromKickoff'])>=60:raise ValueError('Hourly forecast does not align to verified kickoff')
freeze_json(target,{'oldCfbProbeStatus':'withdrawn_as_game_weather_valid_time_followed_midnight_placeholder','oldCfbForecastValidAt':cfb['fields'][0]['forecastValidAt'],'verifiedCfbKickoff':box['scheduledStart'],'correctedCfbCase':updated,'nflCaseStatus':'original_valid_time_matches_verified_kickoff','modelFeaturesChanged':False,'probabilityResultsChanged':False,'interpretation':'Source provenance and event-time alignment are separate checks. Corrected evidence is not silently inserted into a forecast already produced.'});print(json.dumps({'eventId':cfb['eventId'],'leadHours':lead,'validOffsetMinutesFromKickoff':updated['validOffsetMinutesFromKickoff'],'sourcePublication':updated['fields'][0]['sourceVersionPublishedAt'],'probabilityResultsChanged':False}))
