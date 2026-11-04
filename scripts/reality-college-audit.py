"""Real NCAA replay from the existing public adapter; retrospective only."""
import sys,json,time,hashlib,urllib.request,argparse
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modeling.cfb_public_research import source_file,normalize_public_cfb
from modeling.cfb_simulator import fit_cfb_csv,simulate_cfb
def run(date,out):
    url='https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=80&limit=200&dates='+date
    data=json.load(urllib.request.urlopen(url,timeout=30));events=[e for e in data['events'] if e.get('status',{}).get('type',{}).get('completed')]
    # Predeclare one opponent pair before inspecting projections/errors.
    candidates=[e for e in events if {str(c['team']['id']) for c in e['competitions'][0]['competitors']}=={'194','130'}]
    if len(candidates)!=1:raise ValueError('Exact published Michigan/Ohio State event unavailable for this date')
    e=candidates[0];c=e['competitions'][0];teams={v['homeAway']:v['team'] for v in c['competitors']};season=int(e['season']['year']);week=int(e['week']['number']);source=source_file(season);corpus=normalize_public_cfb(source['path'],str(teams['home']['id']),str(teams['away']['id']),e['date'])
    game={'id':'cfb:espn:'+e['id'],'sport':'CFB','season':season,'week':week,'startTime':e['date'],'home':{'id':'cfb:espn:'+teams['home']['id'],'name':teams['home']['displayName']},'away':{'id':'cfb:espn:'+teams['away']['id'],'name':teams['away']['displayName']}}
    if game['id'] in corpus['historicalGameIds']:raise ValueError('Held-out game entered training')
    model=fit_cfb_csv(corpus['csv'],source['url'],corpus['asOf'])['model'];start=time.process_time();result=simulate_cfb(model,game['home']['id'],game['away']['id'],10000,14013,game['startTime'],representative_games=1);cpu=time.process_time()-start;created=datetime.now(timezone.utc).isoformat()
    frozen={'schemaVersion':1,'game':game,'analysisId':'historical-'+hashlib.sha256((game['id']+model['sha256']).encode()).hexdigest(),'predictedAt':created,'inputVersion':model['sha256'],'modelVersion':result['modelVersion'],'result':result,'research':{'source':source['url'],'sourceVersion':source['sha256'],'historicalPublicationVerified':False,'playerCatalog':corpus['playerCatalog'],'historicalGameIds':corpus['historicalGameIds'],'limitations':['Retrospective NCAA play model; original publication, injuries, roster continuity and weather assumptions are incompletely verified.']},'retrospective':True}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(frozen,separators=(',',':')));out.with_suffix('.input.json').write_text(json.dumps(model,separators=(',',':')));print(json.dumps({'gameId':game['id'],'sport':'CFB','simulations':10000,'cpuSeconds':cpu,'inputVersion':model['sha256'],'historicalGames':len(corpus['historicalGameIds']),'mode':'retrospective','source':source['url']}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--date',default='20251129');p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.date,a.out)
