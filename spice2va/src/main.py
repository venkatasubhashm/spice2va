import argparse
import sys
import os
from .parser import SpiceParser
from .physics import validate_physics
from .llm.gemini import GeminiProvider, VerilogAModelOutput
from .llm.groq import GroqProvider
from .generator import Generator
from .validator import Validator
from .simulator import NgspiceSimulator

def main():
    parser = argparse.ArgumentParser(description="Spice2VA: SPICE to Verilog-A Generator")
    parser.add_argument("netlist", help="Path to the SPICE netlist file (.cir)")
    args = parser.parse_args()
    
    print(f"--- Spice2VA Pipeline ---")
    print(f"Reading netlist: {args.netlist}")
    
    try:
        with open(args.netlist, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{args.netlist}' not found.")
        sys.exit(1)
        
    # 1. Parse -> IR
    spice_parser = SpiceParser()
    circuit = spice_parser.parse(content)
    
    print("\n[1] Parsed Circuit (IR):")
    print(f"  Title: {circuit.title}")
    print(f"  Components ({len(circuit.components)}):")
    for comp in circuit.components:
        if comp.type in ('V', 'I') and comp.ac_amplitude is not None:
            print(f"    - {comp.name} [{comp.type}] between {comp.nodes}: {comp.value_str} (ac_amplitude: {comp.ac_amplitude})")
        else:
            print(f"    - {comp.name} [{comp.type}] between {comp.nodes}: {comp.value_str} (parsed: {comp.value})")
    
    if circuit.models:
        print(f"  Models ({len(circuit.models)}):")
        for m in circuit.models:
            print(f"    - {m.name} [{m.model_type}]: {m.params}")
            
    print(f"  Directives ({len(circuit.directives)}):")
    for d in circuit.directives:
        print(f"    - .{d.type} {' '.join(d.params)}")
        
    # 2. Deterministic Physics Validation
    print("\n[2] Deterministic Physics Validation:")
    phys_results = validate_physics(circuit)
    if not phys_results:
        print("  No recognizable simple topology found for deterministic checks.")
    else:
        for k, v in phys_results.items():
            if k == 'rc_tau' and isinstance(v, float):
                print(f"  - {k}: {v * 1000:.2f} ms")
            elif k == 'V_T' and isinstance(v, float):
                print(f"  - {k}: {v * 1000:.2f} mV")
            elif isinstance(v, float):
                if v == 0.0:
                    print(f"  - {k}: 0.00")
                elif abs(v) < 1e-3 or abs(v) > 1e4:
                    print(f"  - {k}: {v:.2e}")
                else:
                    print(f"  - {k}: {v:.2f}")
            else:
                print(f"  - {k}: {v}")
                
    # 3. LLM Analysis & Generation
    print("\n[3] LLM Analysis & Generation:")
    llm_provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    
    if llm_provider == "gemini":
        if not os.environ.get("GEMINI_API_KEY"):
            print("  -> Error: GEMINI_API_KEY environment variable not set.")
            provider = None
        else:
            provider = GeminiProvider()
    elif llm_provider == "groq":
        if not os.environ.get("GROQ_API_KEY"):
            print("  -> Error: GROQ_API_KEY environment variable not set.")
            provider = None
        else:
            provider = GroqProvider()
    else:
        print(f"  -> Error: Unknown LLM_PROVIDER '{llm_provider}'. Supported values are 'gemini', 'groq'.")
        provider = None
        
    if provider:
        print(f"  [LLM] Provider: {llm_provider.capitalize()}")
        print(f"  [LLM] Model: {provider.model_name}")
        print("  -> Calling LLM API...")
    
    # Build prompt
    ir_text = f"Title: {circuit.title}\nComponents:\n"
    for comp in circuit.components:
        ir_text += f"  - {comp.name} [{comp.type}] between {comp.nodes}: {comp.value_str} (parsed val: {comp.value}, ac_amp: {comp.ac_amplitude})\n"
        
    phys_text = ""
    if phys_results:
        phys_text = "Deterministic Physics Insights:\n"
        for k, v in phys_results.items():
            phys_text += f"  - {k}: {v}\n"
            
    prompt = f"""
You are an expert analog circuit designer and Verilog-A modeler.
Translate the following SPICE circuit Intermediate Representation (IR) into a physically meaningful Verilog-A behavioral model.

Circuit IR:
{ir_text}

{phys_text}
"""
    if provider:
        try:
            model_output = provider.generate_structured(prompt, VerilogAModelOutput)
            print("  -> Successfully generated structured output.")
            
            # 4. Validation
            print("\n[4] Validation Checks:")
            validator = Validator()
            val_report = validator.validate(circuit, phys_results, model_output)
            print(f"  - Structural:  {val_report.structural}")
            print(f"  - Topology:    {val_report.topology}")
            print(f"  - Parameters:  {val_report.parameters}")
            print(f"  - Physics:     {val_report.physics}")
            print(f"  - Abstraction: {val_report.abstraction}")
            print(f"  -> OVERALL:    {val_report.overall}")
            
            # 5. Generate Output Files
            print("\n[5] Generated Files:")
            generator = Generator(output_dir="examples/output")
            basename = os.path.basename(args.netlist).replace(".cir", "")
            va_path = generator.save(basename, model_output, phys_results, val_report)
            print(f"  - Verilog-A model saved to: {va_path}")
            print(f"  - Analysis report saved to: {va_path.replace('.va', '_analysis.md')}")
            
        except Exception as e:
            print(f"  -> Error calling LLM: {e}")
    
    # 6. Simulator Status
    print("\n[6] Dynamic Simulation:\n")
    print("Reference Simulator:")
    simulator = NgspiceSimulator()
    if simulator.is_available():
        print("- ngspice: AVAILABLE")
        sim_result = simulator.run_reference(args.netlist)
        if sim_result.is_success:
            print(f"- Analysis: {sim_result.analysis_type}")
            print("- Reference simulation: PASS\n")
            
            print("Reference Validation:")
            if sim_result.analysis_type == "AC":
                lf_gain = sim_result.ac_metrics.get('lf_gain', 0.0)
                measured_cutoff = sim_result.ac_metrics.get('cutoff_hz', 0.0)
                expected_cutoff = phys_results.get('rc_cutoff_hz', 0.0) if phys_results else 0.0
                
                print(f"- Expected fc: {expected_cutoff:.2f} Hz")
                print(f"- ngspice fc: {measured_cutoff:.2f} Hz")
                
                if expected_cutoff > 0 and measured_cutoff > 0:
                    error_pct = abs(measured_cutoff - expected_cutoff) / expected_cutoff * 100
                    print(f"- Error: {error_pct:.4f} %")
                    if error_pct < 5.0:
                        print("- Result: VERIFIED")
                    else:
                        print("- Result: FAIL")
                else:
                    print("- Error: N/A")
                    print("- Result: FAIL")
            else:
                # OP Comparison
                valid_nodes = set(n.lower() for c in circuit.components for n in c.nodes)
                valid_branches = set(f"{c.name.lower()}#branch" for c in circuit.components if c.type == 'V')
                
                ref_vd = sim_result.results.get('out', 0.0)
                ref_id = abs(sim_result.results.get('v1#branch', 0.0))
                
                print("Reference (ngspice):")
                for k, v in sim_result.results.items():
                    if (k in valid_nodes or k in valid_branches) and k not in ('0', 'v(0)'):
                        print(f"- {k} = {v:.4e}")
                        
                print("\nDeterministic model:")
                det_vd = phys_results.get('Vd', 0.0)
                det_id = phys_results.get('Id', 0.0)
                print(f"- Vd = {det_vd:.4e}")
                print(f"- Id = {det_id:.4e}")
                
                print("\nComparison:")
                vd_err = abs(ref_vd - det_vd)
                id_err = abs(ref_id - det_id)
                print(f"- Vd error = {vd_err:.4e}")
                print(f"- Id error = {id_err:.4e}")
                if vd_err < 1e-2 and id_err < 1e-4:
                    print("- Result: VERIFIED")
                else:
                    print("- Result: FAIL")
        else:
            print("- Reference simulation: FAIL")
            if sim_result.stderr:
                print(f"  Error: {sim_result.stderr.strip()}")
            elif sim_result.stdout:
                print("  Error in stdout. Run manually to check.")
    else:
        print("- ngspice: NOT_AVAILABLE")
        print("- Reference simulation: NOT_AVAILABLE")
        
    print("\nGenerated Verilog-A:")
    print("- Simulation: NOT_AVAILABLE")
    
    print("\nOverall:")
    print("- Verilog-A physics verification: NOT_VERIFIED")
    
if __name__ == "__main__":
    main()
