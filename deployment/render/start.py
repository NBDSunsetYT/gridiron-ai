"""Render free web startup: one private compute worker behind bearer auth.
No provider key or shared simulation credential is baked into the image.
"""
import os
import sys


def configuration(environ=None):
    values = dict(os.environ if environ is None else environ)
    token = values.get('SIMULATION_SERVICE_TOKEN', '')
    if len(token) < 32:
        raise ValueError('A stable server-only SIMULATION_SERVICE_TOKEN of at least32 characters is required')
    raw_port = values.get('PORT', '10000')
    if not raw_port.isdigit() or not 1 <= int(raw_port) <= 65535:
        raise ValueError('PORT must be a valid TCP port')
    # Native BLAS thread pools must not oversubscribe the free 0.1CPU instance.
    values.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    return values, int(raw_port)


def main():
    try:
        values, port = configuration()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    os.environ.update(values)
    import uvicorn
    uvicorn.run('modeling.service:app', host='0.0.0.0', port=port, workers=1,
                proxy_headers=True, forwarded_allow_ips='*', access_log=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
