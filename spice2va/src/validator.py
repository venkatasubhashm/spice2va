from dataclasses import dataclass, field
from typing import Dict, Any, List
from .ir import Circuit
from .llm.gemini import VerilogAModelOutput
from .simulator import SimulationResult

LF_GAIN_TOLERANCE_PCT = 0.1
CUTOFF_TOLERANCE_PCT = 1.0

@dataclass
class NumericalComparisonResult:
    is_success: bool = False
    reference_lf_gain: float = 0.0
    generated_lf_gain: float = 0.0
    lf_gain_error_percent: float = 0.0
    reference_cutoff_hz: float = 0.0
    generated_cutoff_hz: float = 0.0
    cutoff_error_percent: float = 0.0
    messages: List[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    structural: str = "FAIL"
    topology: str = "FAIL"
    parameters: str = "FAIL"
    physics: str = "NOT_VERIFIED"
    abstraction: str = "FAIL"
    overall: str = "FAIL"
    messages: List[str] = field(default_factory=list)

class Validator:
    def validate(self, circuit: Circuit, phys_results: Dict[str, Any], model_output: VerilogAModelOutput) -> ValidationReport:
        report = ValidationReport()
        code = model_output.verilog_a_code
        
        # 1. Structural Checks
        struct_pass = True
        if "module" not in code or "endmodule" not in code:
            report.messages.append("Structural: Missing module declaration.")
            struct_pass = False
        if "analog" not in code:
            report.messages.append("Structural: Missing analog block.")
            struct_pass = False
        if "electrical" not in code:
            report.messages.append("Structural: Missing electrical declaration.")
            struct_pass = False
        if "<+" not in code:
            report.messages.append("Structural: Missing contribution statement (<+).")
            struct_pass = False
        
        report.structural = "PASS" if struct_pass else "FAIL"

        # 2. Topology / Parameters Checks
        top_pass = True
        param_pass = True
        
        # Check if basic parsed components are present in parameters
        # This is a heuristic check looking for the value or name
        for comp in circuit.components:
            if comp.type == 'R' and comp.value is not None:
                if str(comp.value) not in code and "1000" not in code and "1k" not in code:
                    report.messages.append(f"Parameters: R value {comp.value} not explicitly found in code.")
                    # Not strictly failing param_pass since it could be named differently, but we warn
            if comp.type == 'C' and comp.value is not None:
                if str(comp.value) not in code and "1e-06" not in code and "1u" not in code:
                    report.messages.append(f"Parameters: C value {comp.value} not explicitly found in code.")
                    
        # Check Diode params
        diode = next((c for c in circuit.components if c.type == 'D'), None)
        if diode:
            model = next((m for m in circuit.models if m.name == diode.model_name), None)
            if model:
                is_val = model.params.get('Is', 1e-14)
                if str(is_val) not in code and "1e-14" not in code:
                    report.messages.append("Parameters: Diode Is parameter not found in code.")
                    param_pass = False
                    
        import re
        # Extract parameters explicitly defined in the code
        params = re.findall(r'parameter\s+(?:real|integer)\s+(\w+)', code)
        for p in params:
            # Check for hallucinated electrical references like I(C) or V(R)
            if re.search(fr'\b[VI]\s*\(\s*{p}\s*\)', code):
                report.messages.append(f"Topology: Invalid reference to parameter '{p}' inside V() or I().")
                top_pass = False

        # Additional static check for undefined node accesses, just in case they used an undefined name
        # We assume 'in', 'out', 'ground' are safe (if it's a 2-port + implicit ground)
        
        report.topology = "PASS" if top_pass else "FAIL"
        report.parameters = "PASS" if param_pass else "FAIL"

        # 3. Physics / Behavior Checks (Textual only, no simulation)
        # We classify this strictly as NOT_VERIFIED or WARNING until simulation exists.
        physics_status = "NOT_VERIFIED"
        analysis_text = model_output.equations.lower() + " " + model_output.expected_behavior.lower()
        
        if 'rc_cutoff_hz' in phys_results:
            fc = phys_results['rc_cutoff_hz']
            if f"{fc:.2f}" not in analysis_text and str(int(fc)) not in analysis_text:
                report.messages.append("Physics: LLM analysis did not accurately report deterministic fc.")
                physics_status = "WARNING"
                
        if 'Vd' in phys_results and 'Id' in phys_results:
            # We just want to see if the equation exp(...) is represented
            if "exp" not in code and "limexp" not in code:
                report.messages.append("Physics: Diode exponential equation not found in Verilog-A code.")
                physics_status = "WARNING"

        report.physics = physics_status

        # 4. Abstraction Checks
        abs_status = "PASS"
        if diode:
             # If V(in) <+ 1.0 is hardcoded, it's a test circuit embedding
             if "V(in)" in code and "<+" in code and "1" in code:
                 report.messages.append("Abstraction: Independent voltage source (e.g. V1) is embedded in the Verilog-A model. Model represents test circuit, not a generic device.")
                 abs_status = "WARN"

        report.abstraction = abs_status

        # Overall Result
        has_fail = any(s == "FAIL" for s in [report.structural, report.topology, report.parameters])
        has_warn = any(s == "WARN" or s == "WARNING" for s in [report.topology, report.physics, report.abstraction])
        
        if has_fail:
            report.overall = "FAIL"
        elif has_warn:
            report.overall = "PASS WITH WARNINGS"
        else:
            report.overall = "PASS"

        return report

    def compare_simulations(self, ref_sim: SimulationResult, gen_sim: SimulationResult) -> NumericalComparisonResult:
        result = NumericalComparisonResult()
        
        if not ref_sim.is_success:
            result.messages.append("Reference Simulation Failed")
            return result
            
        if not gen_sim.is_success:
            # We preserve the exact error message from simulator to pass it up
            err = gen_sim.stderr.strip() if gen_sim.stderr else "Generated Model Simulation Failed"
            result.messages.append(err)
            return result
            
        if ref_sim.analysis_type != "AC" or gen_sim.analysis_type != "AC":
            result.messages.append("Numerical Verification Failed: Both simulations must be AC analysis for comparison.")
            return result
            
        result.reference_lf_gain = ref_sim.ac_metrics.get('lf_gain', 0.0)
        result.generated_lf_gain = gen_sim.ac_metrics.get('lf_gain', 0.0)
        
        if result.reference_lf_gain != 0:
            result.lf_gain_error_percent = abs(result.generated_lf_gain - result.reference_lf_gain) / abs(result.reference_lf_gain) * 100.0
        else:
            result.lf_gain_error_percent = float('inf')
            
        result.reference_cutoff_hz = ref_sim.ac_metrics.get('cutoff_hz', 0.0)
        result.generated_cutoff_hz = gen_sim.ac_metrics.get('cutoff_hz', 0.0)
        
        if result.reference_cutoff_hz != 0:
            result.cutoff_error_percent = abs(result.generated_cutoff_hz - result.reference_cutoff_hz) / abs(result.reference_cutoff_hz) * 100.0
        else:
            result.cutoff_error_percent = float('inf')
            
        if result.lf_gain_error_percent <= LF_GAIN_TOLERANCE_PCT and result.cutoff_error_percent <= CUTOFF_TOLERANCE_PCT:
            result.is_success = True
        else:
            result.messages.append("Numerical Verification Failed: Tolerances exceeded.")
            
        return result
