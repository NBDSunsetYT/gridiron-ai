"""Railway runtime: one private quantitative worker with actual dual-stack HTTP."""
import os
import socket
import sys


def configuration(environment=None):
    env=os.environ if environment is None else environment
    token=env.get('SIMULATION_SERVICE_TOKEN','')
    if len(token)<32:
        raise ValueError('A stable server-only simulation token of at least 32 characters is required')
    port=int(env.get('PORT','8080'))
    if not 1<=port<=65535:
        raise ValueError('PORT must be a valid TCP port')
    return port


def listener(port):
    # Legacy Railway environments have IPv6-only private networking. A plain
    # Uvicorn --host 0.0.0.0 listener cannot accept it; :: alone can be v6-only.
    sock=socket.socket(socket.AF_INET6,socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    sock.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,0)
    sock.bind(('::',port))
    sock.listen(2048)
    return sock


def main():
    sys.path.insert(0,os.getcwd())
    import uvicorn
    port=configuration()
    sock=listener(port)
    config=uvicorn.Config('modeling.service:app',host='::',port=port,workers=1,
                          access_log=False,timeout_graceful_shutdown=240)
    try:
        uvicorn.Server(config).run(sockets=[sock])
    finally:
        sock.close()


if __name__=='__main__':
    main()
