import unittest
import os
from unittest.mock import patch, mock_open, MagicMock

from src.validator import Validator
from src.simulator import SimulationResult, NgspiceSimulator
from src.ir import Circuit, Component, Directive

class TestNumericalComparison(unittest.TestCase):
    def setUp(self):
        self.validator = Validator()
        
    def test_numerical_comparison_pass(self):
        r1 = SimulationResult(is_success=True, analysis_type="AC", ac_metrics={"lf_gain": 1.0, "cutoff_hz": 100.0})
        r2 = SimulationResult(is_success=True, analysis_type="AC", ac_metrics={"lf_gain": 0.9995, "cutoff_hz": 99.5})
        
        result = self.validator.compare_simulations(r1, r2)
        self.assertTrue(result.is_success)
        self.assertAlmostEqual(result.lf_gain_error_percent, 0.05)
        self.assertAlmostEqual(result.cutoff_error_percent, 0.5)
        
    def test_numerical_comparison_fail_gain(self):
        r1 = SimulationResult(is_success=True, analysis_type="AC", ac_metrics={"lf_gain": 1.0, "cutoff_hz": 100.0})
        r2 = SimulationResult(is_success=True, analysis_type="AC", ac_metrics={"lf_gain": 0.998, "cutoff_hz": 100.0})
        
        result = self.validator.compare_simulations(r1, r2)
        self.assertFalse(result.is_success)
        self.assertTrue(any("Tolerances exceeded" in m for m in result.messages))
        
    def test_numerical_comparison_fail_cutoff(self):
        r1 = SimulationResult(is_success=True, analysis_type="AC", ac_metrics={"lf_gain": 1.0, "cutoff_hz": 100.0})
        r2 = SimulationResult(is_success=True, analysis_type="AC", ac_metrics={"lf_gain": 1.0, "cutoff_hz": 98.0})
        
        result = self.validator.compare_simulations(r1, r2)
        self.assertFalse(result.is_success)
        
    def test_numerical_comparison_sim_failure(self):
        r1 = SimulationResult(is_success=True, analysis_type="AC")
        r2 = SimulationResult(is_success=False, stderr="Simulation failed internally")
        
        result = self.validator.compare_simulations(r1, r2)
        self.assertFalse(result.is_success)
        self.assertTrue(any("Simulation failed internally" in m for m in result.messages))

class TestSimulatorExtraction(unittest.TestCase):
    def setUp(self):
        self.simulator = NgspiceSimulator()
        self.circuit = Circuit(
            components=[
                Component(name="R1", type="R", nodes=["in", "out"], value_str="1k", value=1000.0),
                Component(name="C1", type="C", nodes=["out", "0"], value_str="1u", value=1e-6),
                Component(name="V1", type="V", nodes=["in", "0"], value_str="1", value=1.0, ac_amplitude=1.0)
            ],
            directives=[
                Directive(type="ac", params=["dec", "100", "1", "100k"])
            ]
        )
        
    def test_extract_module_interface(self):
        code = "module my_filter(in, out);\nparameter real R = 1000;\nparameter real C = 1e-6;\nendmodule"
        with patch("builtins.open", mock_open(read_data=code)):
            mod_name, ports, params, err = self.simulator._extract_module_interface("dummy.va")
            self.assertEqual(mod_name, "my_filter")
            self.assertEqual(ports, ["in", "out"])
            self.assertEqual(params, ["R", "C"])
            self.assertIsNone(err)

    @patch("shutil.which")
    @patch("os.path.exists")
    @patch("subprocess.run")
    @patch("tempfile.TemporaryDirectory")
    def test_run_generated_model_mapping(self, mock_tempdir, mock_run, mock_exists, mock_which):
        # Setup mocks
        mock_which.return_value = "/bin/openvaf"
        mock_exists.return_value = True
        
        ctx = MagicMock()
        ctx.__enter__.return_value = "/tmp"
        mock_tempdir.return_value = ctx
        
        proc1 = MagicMock()
        proc1.returncode = 0
        proc2 = MagicMock()
        proc2.returncode = 0
        proc2.stdout = "Index frequency vm(out)\n0 1.0 1.0\n1 10.0 0.5"
        proc2.stderr = ""
        mock_run.side_effect = [proc1, proc2]
        
        code = "module my_filter(in, out);\nparameter real R = 1000;\nparameter real C = 1e-6;\nendmodule"
        with patch("builtins.open", mock_open(read_data=code)) as mock_file:
            res = self.simulator.run_generated_model("dummy.va", self.circuit)
            
            # Verify the written testbench
            written_content = ""
            for call in mock_file().write.call_args_list:
                written_content += call[0][0]
                
            self.assertTrue(res.is_success)
            self.assertIn("N1 in out my_filter_model", written_content)
            self.assertIn(".model my_filter_model my_filter (R=1000.0 C=1e-06)", written_content)
            self.assertIn("V1 in 0 DC 0 AC 1.0", written_content)
            self.assertIn("ac dec 100 1 100k", written_content)
            

    @patch("shutil.which")
    @patch("os.path.exists")
    @patch("subprocess.run")
    @patch("tempfile.TemporaryDirectory")
    def test_run_generated_model_port_mapping_fail(self, mock_tempdir, mock_run, mock_exists, mock_which):
        mock_which.return_value = "/bin/openvaf"
        mock_exists.return_value = True
        
        ctx = MagicMock()
        ctx.__enter__.return_value = "/tmp"
        mock_tempdir.return_value = ctx
        
        proc1 = MagicMock()
        proc1.returncode = 0
        mock_run.side_effect = [proc1]
        
        code = "module my_filter(input_node, output_node);\nparameter real R = 1000;\nparameter real C = 1e-6;\nendmodule"
        with patch("builtins.open", mock_open(read_data=code)):
            res = self.simulator.run_generated_model("dummy.va", self.circuit)
            self.assertFalse(res.is_success)
            self.assertTrue("Port Mapping Failed" in res.stderr)
            self.assertTrue("input_node" in res.stderr)

if __name__ == "__main__":
    unittest.main()
