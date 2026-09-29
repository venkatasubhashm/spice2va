import unittest
from src.ir import Circuit, Component
from src.validator import Validator
from src.llm.gemini import VerilogAModelOutput

class TestValidator(unittest.TestCase):
    def setUp(self):
        self.validator = Validator()
        self.circuit = Circuit(
            title="RC Low Pass",
            components=[
                Component(name="R1", type="R", nodes=["in", "out"], value_str="1k", value=1000.0),
                Component(name="C1", type="C", nodes=["out", "0"], value_str="1u", value=1e-6)
            ]
        )
        self.phys_results = {}

    def test_hallucinated_parameter_access(self):
        # This code contains the hallucinated I(C) which should be caught by the validator
        bad_code = """`include "disciplines.vams"
module rc_lowpass(in, out);
    inout in, out;
    electrical in, out;
    parameter real R = 1000;
    parameter real C = 1e-6;
    analog begin
        V(out) <+ V(in) - R*I(C);
        I(C) <+ C*ddt(V(out));
    end
endmodule"""
        
        output = VerilogAModelOutput(
            circuit_summary="Test", topology="Test", equations="Test", assumptions="Test",
            verilog_a_code=bad_code, validation_plan="Test", expected_behavior="Test"
        )
        
        report = self.validator.validate(self.circuit, self.phys_results, output)
        
        self.assertEqual(report.topology, "FAIL")
        self.assertTrue(any("Invalid reference to parameter 'C' inside V() or I()" in msg for msg in report.messages))

    def test_valid_topology(self):
        # A valid implementation using KCL and explicit branch currents
        good_code = """`include "disciplines.vams"
module rc_lowpass(in, out);
    inout in, out;
    electrical in, out;
    parameter real R = 1000;
    parameter real C = 1e-6;
    analog begin
        I(in, out) <+ (V(in) - V(out)) / R;
        I(out) <+ C*ddt(V(out));
    end
endmodule"""
        
        output = VerilogAModelOutput(
            circuit_summary="Test", topology="Test", equations="Test", assumptions="Test",
            verilog_a_code=good_code, validation_plan="Test", expected_behavior="Test"
        )
        
        report = self.validator.validate(self.circuit, self.phys_results, output)
        
        self.assertEqual(report.topology, "PASS")
        self.assertEqual(report.overall, "PASS")

if __name__ == "__main__":
    unittest.main()
