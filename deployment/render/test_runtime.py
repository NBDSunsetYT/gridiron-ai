"""SYNTHETIC configuration tests; not NFL forecasts or a remote deployment."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('render_start', Path(__file__).with_name('start.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RenderStartup(unittest.TestCase):
    def test_default_and_dynamic_port_preserve_stable_token_without_oversubscribing_cpu(self):
        value, port = module.configuration({'SIMULATION_SERVICE_TOKEN': 'SYNTHETIC_ONLY_' * 4})
        self.assertEqual(port, 10000)
        self.assertEqual(value['OMP_NUM_THREADS'], '1')
        self.assertEqual(module.configuration({'SIMULATION_SERVICE_TOKEN': 'SYNTHETIC_ONLY_' * 4, 'PORT': '18888'})[1], 18888)

    def test_missing_secret_and_invalid_port_fail_before_startup(self):
        for values in ({}, {'SIMULATION_SERVICE_TOKEN': 'short'},
                       {'SIMULATION_SERVICE_TOKEN': 'SYNTHETIC_ONLY_' * 4, 'PORT': '0'},
                       {'SIMULATION_SERVICE_TOKEN': 'SYNTHETIC_ONLY_' * 4, 'PORT': 'abc'}):
            with self.assertRaises(ValueError):
                module.configuration(values)


if __name__ == '__main__':
    unittest.main()
