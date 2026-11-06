"""Private inference boundary. Provider keys never enter this service's bodies.

NBA source preparation is bounded and shared by the Next.js distributed lease.
Football fitting is an offline/background operation: no historical rebuild is
triggered by opening a player page. Signed candidates remain unpromoted.
"""
import asyncio
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request
import urllib.error
from fastapi import APIRouter,Header,HTTPException,Request


def make_engine_router(authorize,read_body,guarded,signature,verify_artifact):
    router=APIRouter()

    @router.get('/v15/status')
    async def status(authorization:str|None=Header(default=None)):
        authorize(authorization)
        return {'version':'15.0.0','sports':['NFL','CFB','NBA'],'productionPromotions':0,
            'football':'independent possession/state candidate; offline fitting and signed inference',
            'nba':'independent possession/rotation candidate; not a football model',
            'validated':False,'simulationCounts':[10000,50000,100000]}

    @router.post('/nba/prepare')
    async def prepare(request:Request,authorization:str|None=Header(default=None)):
        authorize(authorization);data=await read_body(request)
        if set(data)-{'cutoff'}:raise HTTPException(422,'Unsupported NBA preparation fields')
        cutoff=datetime.now(timezone.utc)
        if data.get('cutoff'):
            raise HTTPException(422,'Public NBA preparation uses the current server time; historical tests use the offline audit')
        def work():
            from .nba_v15 import load_nba,fit_nba
            season=cutoff.year+int(cutoff.month>=7);sources=[];paths={}
            for key,tag,prefix in [('players','espn_nba_player_boxscores','player_box'),('teams','espn_nba_team_boxscores','team_box'),('plays','espn_nba_pbp','play_by_play')]:
                url=f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/{tag}/{prefix}_{season}.parquet'
                path=Path(tempfile.gettempdir())/f'gridiron-nba-v15-{key}-{season}.parquet'
                checked=datetime.now(timezone.utc).isoformat()
                if not path.exists() or path.stat().st_mtime<cutoff.timestamp()-6*3600:
                    temp=path.with_suffix('.partial')
                    try:
                        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'GRIDIRON-AI-NBA/15'}),timeout=30) as response,temp.open('wb') as output:
                            size=0
                            while chunk:=response.read(1024*1024):
                                size+=len(chunk)
                                if size>40_000_000:raise ValueError('NBA historical source exceeds the worker download bound')
                                output.write(chunk)
                        temp.replace(path)
                    except Exception:
                        temp.unlink(missing_ok=True)
                        raise HTTPException(503,'The current-season NBA source could not be retrieved; no earlier-season roster was substituted') from None
                paths[key]=path;sources.append({'url':url,'collectedAt':checked,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            games=load_nba(paths['players'],paths['teams'],paths['plays'])
            material_sources=[{'url':s['url'],'sha256':s['sha256']} for s in sources]
            model=fit_nba(games,cutoff.isoformat(),hashlib.sha256(json.dumps(material_sources,sort_keys=True).encode()).hexdigest())
            model['sources']=sources;model['signatureVersion']='numeric-canonical-v1';model['signature']=signature(model)
            return {'sport':'NBA','model':model,'preparedAt':cutoff.isoformat(),'modelVersion':model['version'],'calibrated':False}
        return await asyncio.to_thread(guarded,work)

    @router.post('/nba/analyze')
    async def nba(request:Request,authorization:str|None=Header(default=None)):
        authorize(authorization);data=await read_body(request)
        if set(data)-{'model','home','away','eventStart','simulations','seed','lineups'}:raise HTTPException(422,'Unsupported NBA inference fields')
        model=data.get('model')
        if not isinstance(model,dict) or not verify_artifact(model):raise HTTPException(422,'A signed NBA artifact is required')
        from .nba_v15 import VERSION,simulate_nba
        if model.get('version')!=VERSION or model.get('sport')!='NBA':raise HTTPException(422,'Football artifacts cannot enter the NBA engine')
        if model.get('syntheticEvidence') and (os.environ.get('VERCEL')=='1' or os.environ.get('RENDER')=='true'):raise HTTPException(422,'Synthetic mechanical fixtures cannot generate deployed NBA forecasts')
        count=data.get('simulations',10000)
        if count not in (10000,50000,100000):raise HTTPException(422,'Choose 10,000, 50,000 or 100,000 complete NBA games')
        return await asyncio.to_thread(guarded,lambda:simulate_nba(model,data.get('home'),data.get('away'),data.get('eventStart'),count,data.get('seed',15002),data.get('lineups')))

    @router.post('/v15/football/analyze')
    async def football(request:Request,authorization:str|None=Header(default=None)):
        authorize(authorization);data=await read_body(request)
        if set(data)-{'model','home','away','eventStart','simulations','seed','lineups'}:raise HTTPException(422,'Unsupported football inference fields')
        model=data.get('model')
        if not isinstance(model,dict) or not verify_artifact(model):raise HTTPException(422,'A signed candidate artifact is required; no per-visitor historical rebuild is performed')
        from .football_v15 import VERSION,simulate_football
        if model.get('version') not in (VERSION,'football-possession-hurdle-candidate-15.1.0','football-possession-candidate-15.0.0') or model.get('sport') not in ('NFL','CFB'):raise HTTPException(422,'A separate NFL or CFB fitted candidate is required')
        return await asyncio.to_thread(guarded,lambda:simulate_football(model,data.get('home'),data.get('away'),data.get('eventStart'),data.get('simulations',10000),data.get('seed',15001),data.get('lineups'),batch_size=2000))
    return router
