"""Private CFB-only fit/compute boundary; no provider key reaches the browser."""
import asyncio
import os

from fastapi import APIRouter, Header, HTTPException, Request

from .cfb_simulator import (fit_cfb_csv, simulate_cfb, MODEL_VERSION,
                            ENGINE_VERSION, RULES_VERSION, RULES_URL)


def make_cfb_router(authorize, read_body, guarded, signature, verify_artifact):
    router = APIRouter(prefix='/cfb')

    @router.get('/status')
    async def status(authorization: str | None = Header(default=None)):
        authorize(authorization)
        return {'sport':'CFB','engineVersion':ENGINE_VERSION,'modelVersion':MODEL_VERSION,
                'rulesVersion':RULES_VERSION,'rulesSource':RULES_URL,
                'supportedSimulationCounts':[10000,50000,100000],
                'trainedModelAvailable':False,'requiresFittedCFBEvidence':True,
                'message':'The NCAA engine is installed. A source-attested, signed CFB historical artifact is required; engine availability is not a trained forecast.'}

    @router.post('/fit')
    async def fit(request: Request, authorization: str | None = Header(default=None)):
        authorize(authorization)
        data = await read_body(request)
        if set(data)-{'csv','source','asOf','teamMinPlays','options'}:
            raise HTTPException(422,'Unsupported CFB fitting fields')
        def work():
            result = fit_cfb_csv(data.get('csv'),data.get('source'),data.get('asOf'),
                                 data.get('teamMinPlays',100),data.get('options'))
            result['model']['signatureVersion']='numeric-canonical-v1'
            result['model']['signature']=signature(result['model'])
            return result
        return await asyncio.to_thread(guarded,work)

    def run(data):
        allowed={'model','home','away','simulations','seed','eventStart','contracts','scenario',
                 'parameterUncertainty','representativeGames','selectedOutcomes'}
        if set(data)-allowed:
            raise HTTPException(422,'Unsupported CFB assumptions. Unfitted weather, roster, conference and player multipliers are not silently applied.')
        model = data.get('model')
        if not model:
            raise HTTPException(422,{'code':'insufficient_historical_evidence','sport':'CFB',
                'message':'No fitted CFB play-by-play artifact is available. Verified schedules or final scores alone cannot produce complete-game player probabilities.',
                'required':['CFB historical plays with actual game-clock deltas','Verified player-play identities','Source and availability provenance','Sufficient team/down/drive/conversion cohorts']})
        if not verify_artifact(model):
            raise HTTPException(422,'A signed CFB historical artifact is required; fit authorized CFB evidence first')
        if model.get('syntheticEvidence') and (os.environ.get('GRIDIRON_CFB_TEST_MODE')!='1'
                or os.environ.get('VERCEL')=='1' or os.environ.get('RENDER')=='true'):
            raise HTTPException(422,'Synthetic CFB fixtures are restricted to isolated mechanical tests and cannot produce deployed forecasts')
        count=data.get('simulations',10000)
        if isinstance(count,bool) or not isinstance(count,int) or not 1000<=count<=100000:
            raise HTTPException(422,'CFB simulations must be 1000..100000 complete games')
        return guarded(lambda:simulate_cfb(model,data.get('home'),data.get('away'),count,
                        data.get('seed',1),data.get('eventStart'),data.get('contracts'),data.get('scenario'),
                        data.get('parameterUncertainty'),data.get('representativeGames',0),data.get('selectedOutcomes')))

    @router.post('/simulate')
    @router.post('/analyze')
    async def simulate(request: Request, authorization: str | None = Header(default=None)):
        authorize(authorization)
        data=await read_body(request)
        return await asyncio.to_thread(run,data)

    @router.post('/public/analyze')
    async def public_analyze(request: Request, authorization: str | None = Header(default=None)):
        authorize(authorization)
        data=await read_body(request)
        from .cfb_public_research import analyze_cfb_public, CFBSourceUnavailable
        try:
            return await asyncio.to_thread(guarded,lambda:analyze_cfb_public(data))
        except CFBSourceUnavailable:
            raise HTTPException(503,{'code':'source_unavailable','sport':'CFB','message':'The public CFB play source is temporarily unavailable. No empty inventory or replacement forecast is inferred.'},headers={'Retry-After':'60'}) from None

    @router.post('/public/targets')
    async def public_targets(request: Request, authorization: str | None = Header(default=None)):
        authorize(authorization)
        data=await read_body(request)
        from .cfb_public_research import analyze_cfb_targets
        return await asyncio.to_thread(guarded,lambda:analyze_cfb_targets(data))

    @router.post('/public/prepare')
    async def public_prepare(request: Request, authorization: str | None = Header(default=None)):
        authorize(authorization)
        data=await read_body(request)
        from .cfb_public_research import prepare_cfb_public, CFBSourceUnavailable
        try:
            return await asyncio.to_thread(guarded,lambda:prepare_cfb_public(data))
        except CFBSourceUnavailable:
            raise HTTPException(503,{'code':'source_unavailable','sport':'CFB','message':'The public CFB play source is temporarily unavailable. No empty inventory or replacement forecast is inferred.'},headers={'Retry-After':'60'}) from None

    @router.post('/public/prop-history')
    async def public_history(request: Request, authorization: str | None = Header(default=None)):
        authorize(authorization)
        data=await read_body(request)
        from .prop_history import cfb_history
        return await asyncio.to_thread(guarded,lambda:cfb_history(data))

    return router
