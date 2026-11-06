"""V25 Gate 1: execute the original V24 replay without changing its outputs.

No fitting, model selection, market queries, Monte Carlo games, or production
calls. The original replay implementation, seeds and tolerances are retained.
Only its report/image write destinations are redirected to the V25 checkpoint.
"""
import sys, json, hashlib, importlib.util, time, resource, signal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import read, atomic, digest
from modeling.dynamic_v24.runtime import verify_parent

OUT = ROOT/'artifacts/accuracy-v25/stage1'


def validate_preflight(preflight):
    if not preflight or preflight.get('failures'):
        raise ValueError('Missing or inconsistent private V24 baseline artifacts')
    for name, expected in preflight['files'].items():
        path = ROOT/name
        if expected is None or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Private V24 artifact changed or unavailable: '+name)


def same_baseline(expected, observed):
    if not expected or digest(expected) != digest(observed):
        raise ValueError('V24 baseline replay drift; no dependent numerical changes permitted')


def run():
    protocol = read(OUT/'protocol.json')
    if not protocol or protocol.get('operation') != 'read_only_original_v24_replay':
        raise ValueError('Freeze the baseline-replay protocol before execution')
    for name, sha in protocol['code'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != sha:
            raise ValueError('Registered replay code changed')
    preflight = read(OUT/'preflight.json')
    if digest(preflight) != protocol['preflightDigest']:
        raise ValueError('Preflight edition differs from frozen protocol')
    validate_preflight(preflight)
    verify_parent()
    module_path = ROOT/'scripts/replay-specialized-v24.py'
    expected = read(ROOT/'docs/research/specialized-v24-replay.json')
    protected_paths = [ROOT/'docs/research/specialized-v24-replay.json',
                       ROOT/'docs/research/charts/specialized-v24-reliability.png',
                       ROOT/'artifacts/dynamic-v24/completion-final/replay-verification.json']
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected_paths}
    spec = importlib.util.spec_from_file_location('frozen_v24_replay', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reports = []
    allowed = {protected_paths[0], protected_paths[2]}

    def capture(path, value):
        if Path(path) not in allowed:
            raise ValueError('Original replay attempted an unexpected write')
        same_baseline(expected, value)
        reports.append(value)

    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
    original_savefig = Figure.savefig

    def redirected_image(figure, filename, *args, **kwargs):
        if Path(filename) != protected_paths[1]:
            raise ValueError('Unexpected baseline image destination')
        return original_savefig(figure, OUT/'replayed-reliability.png', *args, **kwargs)

    from threadpoolctl import threadpool_limits
    with patch.object(module, 'atomic', capture), patch.object(Figure, 'savefig', redirected_image), threadpool_limits(limits=1):
        result = module.run()
    if len(reports) != 2:
        raise ValueError('Original replay did not produce both expected reports')
    verify_parent()
    if any(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != sha for name, sha in before.items()):
        raise ValueError('Original baseline output changed')
    validate_preflight(preflight)
    freeze_json(OUT/'observed-baseline.json', reports[0])
    return {'gate': 1, 'passed': True, **result,
            'scope': 'original_V24_six_category_frozen_inference_replay_not_new_accuracy',
            'privateArtifactsVerified': preflight['filesChecked'],
            'inheritedArtifactFilesVerified': preflight['inheritedArtifactFilesVerified'],
            'protectedIdsCount': preflight['protectedIdsCount'],
            'baselineDigest': digest(expected), 'replayDigest': digest(reports[0]),
            'originalReplaySourceSHA256': hashlib.sha256(module_path.read_bytes()).hexdigest(),
            'originalOutputsUnchanged': True, 'modelsRefit': 0, 'newGameSimulations': 0,
            'protectedFinalOutcomesOpened': False, 'productionWrites': 0, 'promotions': 0,
            'supersededFitCodeHashEntries': len(preflight['supersededCodeHashes']),
            'fullOriginalTrainingReplayClaimed': False}


def main():
    started = time.monotonic()
    cpu = time.process_time()
    receipt = {'gate': 1, 'passed': False}
    def stop(signum, frame):
        raise TimeoutError('Bounded V25 baseline replay stopped')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGALRM, stop)
    signal.alarm(600)
    resource.setrlimit(resource.RLIMIT_CPU, (300, 305))
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))
    try:
        receipt.update(run())
    except Exception as exc:
        receipt.update(error=type(exc).__name__, reason=str(exc))
        raise
    finally:
        signal.alarm(0)
        receipt.update(cpuSeconds=time.process_time()-cpu, wallSeconds=time.monotonic()-started,
                       peakRssKiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        atomic(OUT/'gate1-receipt.json', receipt)
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
