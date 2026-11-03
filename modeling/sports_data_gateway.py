"""Lightweight Render-only licensed-data gateway; no prediction or ledger code.

Run: uvicorn modeling.sports_data_gateway:app --host 0.0.0.0 --port $PORT
BALLDONTLIE_API_KEY belongs ONLY to this Render environment. Browser and Vercel
callers receive safe data/status DTOs through a different internal bridge token.
"""
import asyncio
import os
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from .balldontlie_nfl import BDLNFLClient, RESOURCES, DOCS
from .sports_data_common import authorize_data_bridge, require_render_runtime, DataProviderError, utc_now
from .performance import install as install_performance, snapshot as performance_snapshot

app = FastAPI(title='GRIDIRON sports-data gateway', docs_url=None, redoc_url=None, openapi_url=None)
install_performance(app)

@app.get('/metrics')
async def metrics(authorization: str | None = Header(default=None)):
    authorize_data_bridge(authorization)
    return performance_snapshot()


def bdl_credential():
    require_render_runtime()  # Before reading the licensed provider credential.
    return os.environ.get('BALLDONTLIE_API_KEY', '')


client = BDLNFLClient(bdl_credential)


@app.exception_handler(DataProviderError)
async def provider_error(request: Request, error: DataProviderError):
    college = request.url.path.startswith('/data/cfb/')
    return JSONResponse({'provider': 'CollegeFootballData' if college else 'BALLDONTLIE',
                         'sport': 'CFB' if college else 'NFL', 'status': 'unavailable',
                         'items': [], 'records': [], 'diagnostic': error.diagnostic()},
                        status_code=error.http_status if error.http_status and 400 <= error.http_status <= 599 else 503)


def unavailable(error):
    return {'provider': 'BALLDONTLIE', 'sport': 'NFL', 'dataFamily': 'sportsbook_reference',
            'status': 'unavailable', 'checkedAt': utc_now(), 'items': [], 'records': [],
            'complete': False, 'nextCursor': None, 'diagnostic': error.diagnostic(),
            'source': {'documentationUrl': DOCS},
            'limitations': ['No request was made to an alternate provider.']}


@app.get('/health')
async def health():
    # Deliberately does not read any licensed provider key or claim API access.
    try:
        require_render_runtime(); render = True
    except DataProviderError:
        render = False
    return {'service': 'GRIDIRON sports-data gateway', 'version': '9.0.0',
            'status': 'ready' if render and len(os.environ.get('GRIDIRON_DATA_BRIDGE_TOKEN', '')) >= 32 else 'unconfigured',
            'providerAccessVerified': False, 'secretLocation': 'Render environment only'}


@app.get('/data/nfl/status')
async def status(authorization: str | None = Header(default=None)):
    authorize_data_bridge(authorization)
    try:
        if not bdl_credential():
            return unavailable(DataProviderError('credentials_missing', 'BALLDONTLIE credentials are not configured on the Render data gateway.', requires_operator=True))
        return {'provider': 'BALLDONTLIE', 'sport': 'NFL', 'dataFamily': 'sportsbook_reference',
                'status': 'configured', 'checkedAt': utc_now(), 'items': [],
                'diagnostic': {'code': 'credentials_configured_unverified', 'message': 'A Render-side credential is configured. This status check did not verify API authentication or paid endpoint access.',
                               'checkedAt': utc_now(), 'httpStatus': None, 'retryable': False, 'requiresOperator': False},
                'source': {'documentationUrl': DOCS}, 'complete': False}
    except DataProviderError as exc:
        return unavailable(exc)


@app.get('/data/nfl/verify')
async def verify(authorization: str | None = Header(default=None)):
    authorize_data_bridge(authorization)
    # One documented Free-tier request. This never starts a trial or purchase,
    # and success is not evidence of GOAT odds/player-prop entitlement.
    result = await asyncio.to_thread(client.read, 'teams', {})
    return {**result, 'verificationScope': 'Free NFL teams endpoint only; premium odds and player-prop access remains unverified.'}


@app.get('/data/nfl/{resource}')
async def nfl_resource(resource: str, request: Request, authorization: str | None = Header(default=None)):
    authorize_data_bridge(authorization)
    if resource not in RESOURCES:
        raise HTTPException(404, 'Unsupported NFL provider resource.')
    params = {}
    for key, value in request.query_params.multi_items():
        if key in params:
            params[key] = [*params[key], value] if isinstance(params[key], list) else [params[key], value]
        else:
            params[key] = value
    return await asyncio.to_thread(client.read, resource, params)


# CFBD credentials obey the same Render-only boundary. The CFB provider module
# is separately owned and tested; it does not change existing NFL simulations.
from .cfbd_data import create_cfbd_router
app.include_router(create_cfbd_router(authorize_data_bridge))

# Primary football sportsbook provider. Legacy BDL routes remain available for
# compatibility; they are not a fallback for DraftKings Predictions contracts.
from .football_prop_feeds import PropLineClient, choose_feed
prop_line = PropLineClient()

@app.get('/data/props/{sport}')
async def football_props(sport: str, cursor: int = 0, limit: int = 500, authorization: str | None = Header(default=None)):
    authorize_data_bridge(authorization)
    require_render_runtime()
    if sport not in ('NFL','CFB'):
        raise HTTPException(422,'Choose NFL or CFB.')
    # ParlayAPI is deliberately disabled until its official endpoint/schema and
    # entitlement are verified. An access-denied docs page is not a spec.
    if cursor<0 or cursor>50000 or not 1<=limit<=500:raise HTTPException(422,'Choose a bounded page.')
    value=await asyncio.to_thread(choose_feed, lambda selected:prop_line.read_page(selected,cursor,limit), None, sport)
    return {**value,'nextCursor':value.get('nextCursor')}
