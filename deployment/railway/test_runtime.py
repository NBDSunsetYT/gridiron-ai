import importlib.util
from pathlib import Path
import socket
import unittest

spec=importlib.util.spec_from_file_location('railway_quant_runtime',Path(__file__).with_name('start_quant.py'))
runtime=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class RailwayQuantRuntimeTests(unittest.TestCase):
    def test_dynamic_port_and_private_token_configuration(self):
        self.assertEqual(runtime.configuration({'PORT':'9324','SIMULATION_SERVICE_TOKEN':'SYNTHETIC-TEST-ONLY-'+('x'*32)}),9324)
        for env in [{},{'SIMULATION_SERVICE_TOKEN':'SYNTHETIC','PORT':'8000'},{'SIMULATION_SERVICE_TOKEN':'x'*32,'PORT':'65536'}]:
            with self.assertRaises(ValueError):runtime.configuration(env)

    def test_one_socket_accepts_ipv4_and_ipv6_private_health_traffic(self):
        listener=runtime.listener(0)
        listener.settimeout(2)
        port=listener.getsockname()[1]
        try:
            for family,address in [(socket.AF_INET,('127.0.0.1',port)),(socket.AF_INET6,('::1',port))]:
                with socket.socket(family,socket.SOCK_STREAM) as client:
                    client.settimeout(2);client.connect(address);client.sendall(b'fixture')
                    connection,_=listener.accept()
                    with connection:self.assertEqual(connection.recv(16),b'fixture')
        finally:listener.close()


if __name__=='__main__':unittest.main()
