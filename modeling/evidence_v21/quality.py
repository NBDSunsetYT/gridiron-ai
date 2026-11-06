"""Game/player evidence assembly without converting absence to health."""
from datetime import timedelta
from .tiers import classify
from ..accuracy_v20.quality import aware
def record(game,facts,version,player=None,team=None,consistency=None):
    cutoff=(aware(game['at'])-timedelta(minutes=30)).isoformat();source='https://github.com/nflverse/nflverse-data' if game['sport']=='NFL' else 'https://github.com/sportsdataverse';parts={k:{'eventId':game['id'],'source':source,'sourceVersion':version,'publishedAt':None,'retrievedAt':None,'classification':'inferred' if k in ('identity','historical_statistics','participation') else 'unavailable','complete':False,'reason':'Corrected history exists; original pregame publication or complete evidence is not established'} for k in ['identity','historical_statistics','injury','lineup','participation','weather']}
    eligible=[f for f in facts if f['eventId']==game['id'] and (player is None or f.get('playerId')==player) and (team is None or f.get('teamId')==team) and f.get('publishedAt') and aware(f['publishedAt'])<=aware(cutoff)]
    for domain in ['injury','lineup']:
        fs=[f for f in eligible if ('lineup' if f.get('kind')=='projected_depth_chart' else 'injury')==domain]
        if not fs:continue
        f=max(fs,key=lambda f:f['publishedAt']);proven=f.get('confidence') in ('publisher_dated_pregame','publisher_dated_projected','official_timestamped_report');parts[domain]={'eventId':game['id'],'playerId':player,'source':f['source'],'sourceVersion':f['sourceVersion'],'publishedAt':f['publishedAt'] if proven else None,'retrievedAt':f['retrievedAt'],'classification':('projected' if domain=='lineup' else 'confirmed') if proven else 'inferred','complete':player is not None,'status':f.get('status'),'reason':'Report/role evidence only; uncertain or unlisted participants are not healthy by default'}
    q=classify(game['sport'],game['id'],cutoff,parts,player,consistency=consistency or {'identity_scope':True});q['teamId']=team;return q
