"""Optional private simulation service. Run behind TLS on an internal network.

uvicorn modeling.service:app --host 0.0.0.0 --port 8000 --workers 1
"""
import asyncio
import hashlib
import hmac
import json
import os
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from .fit import fit_csv
from .simulator import simulate
from .public_research import ResearchUnavailable
from .cloud_worker import CloudWorker, Config, WorkerError
from .performance import install as install_performance, timed_work, snapshot as performance_snapshot

@asynccontextmanager
async def lifespan(_application):
    yield
    # Request-bound adapters may enter/exit ASGI lifespan for warm invocations.
    # Their compute already finished before returning; do not permanently close
    # a reusable warm dispatcher. Persistent Render processes drain on shutdown.
    if not request_bound_environment():
        await asyncio.to_thread(stop_cloud_worker)


app = FastAPI(title="GRIDIRON empirical simulation service", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
install_performance(app)
lock = threading.Lock()
cloud_worker = None
cloud_worker_lock = threading.Lock()


def secret():
    token = os.environ.get("SIMULATION_SERVICE_TOKEN", "")
    if len(token) < 32:
        raise HTTPException(503, "Simulation service requires a server-side token of at least32 characters")
    return token


def authorize(authorization):
    expected = "Bearer " + secret()
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(401, "Unauthorized")


def signature(model):
    value={k:v for k,v in model.items() if k!='signature'}
    if model.get('signatureVersion')=='numeric-canonical-v1':
        # Browser JSON rewrites1.0 to1 and exponential notation. Encode every
        # numeric leaf as binary64 hex so signed artifacts survive JSON hops.
        def canonical(item):
            if item is None:return ['null']
            if isinstance(item,bool):return ['bool',item]
            if isinstance(item,(int,float)):
                import math
                number=float(item)
                if not math.isfinite(number):raise ValueError('Nonfinite artifact number')
                if number==0:number=0.
                return ['number',number.hex()]
            if isinstance(item,str):return ['string',item]
            if isinstance(item,list):return ['array',[canonical(v) for v in item]]
            if isinstance(item,dict):return ['object',[[k,canonical(item[k])] for k in sorted(item)]]
            raise TypeError('Unsupported model artifact value')
        value=canonical(value)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hmac.new(secret().encode(), payload.encode(), hashlib.sha256).hexdigest()


async def body(request):
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 25_000_000:
            raise HTTPException(413, "Request exceeds25MB")
        chunks.append(chunk)
    raw = b"".join(chunks)
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(400, "Valid JSON required") from exc
    if not isinstance(value, dict):
        raise HTTPException(400, "JSON object required")
    return value


def guarded(work):
    if not lock.acquire(blocking=False):
        raise HTTPException(429, "Another simulation/fit is running; retry after it completes")
    try:
        return timed_work(work)
    except ResearchUnavailable as exc:
        if exc.retryable:
            raise HTTPException(503,'A verified NFL research source is temporarily unavailable. Retry shortly; no replacement statistics or probabilities were invented.',
                                headers={'Retry-After':'15','X-Gridiron-Retryable':'true'}) from exc
        raise HTTPException(422,str(exc),headers={'X-Gridiron-Retryable':'false'}) from exc
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        lock.release()


@app.get("/health")
async def health():
    return {"status": "ready" if len(os.environ.get("SIMULATION_SERVICE_TOKEN", "")) >= 32 else "unconfigured", "model": "pbp-empirical-2.0.0", "trainedData": False,
            "asyncSupported": True, "asyncConfigured": bool(os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_PUBLISHABLE_KEY') and len(os.environ.get('SIMULATION_SERVICE_TOKEN', '')) >= 32)}

@app.get('/metrics')
async def metrics(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return performance_snapshot()


def fit_data(data):
    def work():
        result = fit_csv(data["csv"], data["source"], data["asOf"], data.get("teamMinPlays", 100), data.get('options'))
        result['model']['signatureVersion'] = 'numeric-canonical-v1'
        result['model']['signature'] = signature(result['model'])
        return result
    return guarded(work)


@app.post("/fit")
async def fit(request: Request, authorization: str | None = Header(default=None)):
    authorize(authorization)
    data = await body(request)
    return await asyncio.to_thread(fit_data, data)


@app.post("/simulate")
async def run(request: Request, authorization: str | None = Header(default=None)):
    authorize(authorization)
    data = await body(request)
    return await asyncio.to_thread(simulate_data, data)


@app.post('/public/analyze')
async def public_analysis(request: Request, authorization: str | None = Header(default=None)):
    """Private server-to-server automatic research; guests never send datasets.

    The authenticated web service resolves the requested game from its verified
    shared schedule. The Python service retrieves fixed public nflverse assets.
    Existing owner-scoped fit/simulation endpoints remain unchanged.
    """
    authorize(authorization)
    data = await body(request)
    def work():
        from .public_research import analyze_public
        return analyze_public(data)
    return await asyncio.to_thread(guarded, work)


@app.post('/public/prop-history')
async def public_prop_history(request: Request, authorization: str | None = Header(default=None)):
    authorize(authorization)
    data = await body(request)
    def work():
        from .prop_history import nfl_history
        return nfl_history(data)
    return await asyncio.to_thread(guarded, work)


def simulate_data(data):
    if set(data)-{'model','home','away','simulations','seed','eventStart','contracts','scenario','postseason','parameterUncertainty','representativeGames','selectedOutcomes'}:
        raise HTTPException(422,'Unsupported simulation assumptions. Weather, snap shares and arbitrary player multipliers are not silently applied.')
    model = data.get("model", {})
    try:
        valid = isinstance(model, dict) and isinstance(model.get("signature"), str) and hmac.compare_digest(signature(model), model["signature"])
    except (ValueError, TypeError, OverflowError):
        valid = False
    if not valid:
        raise HTTPException(422, "Model artifact signature invalid; fit historical evidence through /fit first")
    count = data.get("simulations", 10000)
    if not isinstance(count, int) or not 1000 <= count <= 100000:
        raise HTTPException(422, "simulations must be1000..100000")
    def work():
        return simulate(model, data["home"], data["away"], count, data.get("seed", 1), data.get("eventStart"), data.get("contracts"), data.get("scenario"), data.get("postseason", False),parameter_uncertainty=data.get('parameterUncertainty'),representative_games=data.get('representativeGames',0),selected_outcomes=data.get('selectedOutcomes'))
    return guarded(work)


def compute_saved_input(saved):
    data = dict(saved)
    action = data.pop('action', None)
    references = data.pop('injuryEntityKeys', None)
    if references is not None and (not isinstance(references, list) or len(references) > 100 or any(not isinstance(value, str) or not value.strip() or len(value) > 180 for value in references)):
        raise ValueError('Invalid application injury references')
    if action == 'fit':
        if set(data) - {'csv', 'source', 'asOf', 'teamMinPlays', 'options'}:
            raise ValueError('Unsupported fitting assumptions')
        return fit_data(data)
    if action == 'simulate':
        return simulate_data(data)
    raise ValueError('Unsupported saved statistical job')


def get_cloud_worker():
    global cloud_worker
    configuration = Config.from_environment()
    with cloud_worker_lock:
        if cloud_worker is None:
            # Serverless runtimes must not return while daemon threads are still
            # computing. The web caller keeps this private request alive via
            # its supported after-response lifecycle; Render stays asynchronous.
            request_bound = request_bound_environment()
            cloud_worker = CloudWorker(configuration, executor=(lambda work: work()) if request_bound else None)
        elif cloud_worker.config != configuration:
            raise WorkerError('Worker configuration changed; restart compute before accepting another saved job.')
        return cloud_worker


def request_bound_environment():
    return os.environ.get('VERCEL') == '1' or os.environ.get('GRIDIRON_WORKER_REQUEST_LIFETIME') == '1'


@app.post('/jobs', status_code=202)
async def queue_job(request: Request, authorization: str | None = Header(default=None)):
    authorize(authorization)
    data = await body(request)
    if set(data) != {'jobId', 'accessToken'}:
        raise HTTPException(400, 'Supply only the saved job identifier and its current owner access token')
    try:
        worker = get_cloud_worker()
        return await asyncio.to_thread(worker.submit, data['jobId'], data['accessToken'], compute_saved_input)
    except WorkerError as error:
        raise HTTPException(error.status, str(error)) from None
    except Exception:
        raise HTTPException(503, 'Private compute dispatch could not complete. Original saved inputs remain available.') from None


def stop_cloud_worker():
    if cloud_worker is not None:
        cloud_worker.shutdown()


def verify_artifact(model):
    try:
        return isinstance(model,dict) and isinstance(model.get('signature'),str) and hmac.compare_digest(signature(model),model['signature'])
    except (ValueError,TypeError,OverflowError):
        return False


@app.post('/models/benchmark')
async def model_benchmark(request:Request,authorization:str|None=Header(default=None)):
    authorize(authorization);data=await body(request)
    def work():
        from .advanced import benchmark
        result=benchmark(data['csv'],data['source'],data['asOf'],tuple(data.get('holdoutSeasons',[2023,2024,2025])),data.get('firstSeason',2014))
        result['model']['signatureVersion']='numeric-canonical-v1'
        result['model']['signature']=signature(result['model'])
        return result
    return await asyncio.to_thread(guarded,work)


@app.post('/models/predict')
async def model_predict(request:Request,authorization:str|None=Header(default=None)):
    authorize(authorization);data=await body(request);model=data.get('model')
    if not verify_artifact(model):raise HTTPException(422,'Signed game-model artifact required; fit through /models/benchmark first')
    def work():
        from .advanced import predict
        return predict(model,data['home'],data['away'],data['eventStart'],data.get('restDifference'),data.get('division',False))
    return await asyncio.to_thread(guarded,work)


@app.post('/trace')
async def trace(request:Request,authorization:str|None=Header(default=None)):
    authorize(authorization);data=await body(request);model=data.get('model')
    if not verify_artifact(model):raise HTTPException(422,'Signed play-by-play artifact required')
    count=data.get('games',1)
    if not isinstance(count,int) or not 1<=count<=3:raise HTTPException(422,'Representative game count must be1..3')
    def work():
        result=simulate(model,data['home'],data['away'],count,data.get('seed',1),data['eventStart'],scenario=data.get('scenario'),postseason=data.get('postseason',False),representative_games=count)
        return {'games':result['representativeGames'],'modelVersion':result['modelVersion'],'engineVersion':result['engineVersion'],'inputDataVersion':result['inputDataVersion'],'evidenceCutoff':result['evidenceCutoff'],'seed':result['seed'],'purpose':'Representative generated football games for inspection, not probability estimates.'}
    return await asyncio.to_thread(guarded,work)


# NCAA models and transitions remain separate from every existing NFL endpoint.
from .cfb_routes import make_cfb_router
app.include_router(make_cfb_router(authorize,body,guarded,signature,verify_artifact))

# Separate sport-specific candidate boundaries; existing engines and owner
# routes remain available until out-of-sample promotion gates are satisfied.
from .engine_v15_routes import make_engine_router
app.include_router(make_engine_router(authorize,body,guarded,signature,verify_artifact))
