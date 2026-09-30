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

CRITICAL VERILOG-A SEMANTIC RULES:
1. NEVER use parameters as arguments to V() or I(). V() and I() may ONLY reference explicitly declared electrical nodes, ports, or valid branches.
2. DO NOT invent non-existent electrical nodes or branches (e.g., do not write I(C) or V(R) if C and R are parameters). Every electrical quantity MUST correspond to an actual node or branch.
3. PRESERVE TOPOLOGY: The model must preserve the topology represented by the IR. If the circuit has 3 nodes (e.g., in, out, 0), the Verilog-A must preserve the ground/reference behavior.
   NOTE: Our current generator architecture strictly expects a 2-port module (in, out). You MUST use single-ended potentials (e.g., V(out), which implicitly references the global ground) to represent connections to node '0'. Do NOT silently collapse a 3-node circuit into an invalid 2-node model.
4. DO NOT force a particular implementation such as laplace_nd() unless it is physically appropriate. The model should be physically meaningful and compatible with OpenVAF.

Before writing the Verilog-A code, explicitly reason in your expected_behavior/equations about:
- Circuit nodes and branches
- Element constitutive equations
- KCL / current contributions

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
    
    # 6. Dynamic Simulation & Numerical Verification
    print("\n[6] Dynamic Simulation & Numerical Verification:\n")
    simulator = NgspiceSimulator()
    
    ref_sim_result = None
    gen_sim_result = None
    
    print("Reference Simulator (ngspice):")
    if simulator.is_available():
        print("- Status: AVAILABLE")
        ref_sim_result = simulator.run_reference(args.netlist)
        if ref_sim_result.is_success:
            print("- Reference simulation: PASS")
        else:
            print("- Reference simulation: FAIL")
            if ref_sim_result.stderr:
                print(f"  Error: {ref_sim_result.stderr.strip()}")
    else:
        print("- Status: NOT_AVAILABLE")
        print("- Reference simulation: NOT_AVAILABLE")

    print("\nGenerated Model Simulator (OpenVAF + ngspice):")
    if provider and os.path.exists(va_path) and ref_sim_result and ref_sim_result.is_success:
        gen_sim_result = simulator.run_generated_model(va_path, circuit)
        if gen_sim_result.is_success:
            print("- Generated model compilation: PASS")
            print("- Generated model simulation: PASS")
        else:
            err = gen_sim_result.stderr.strip()
            if "OpenVAF Compilation Failed" in err:
                print("- Generated model compilation: FAIL")
                print(f"  Error: {err}")
                print("- Generated model simulation: NOT_RUN")
            elif "Mapping Failed" in err:
                print("- Generated model compilation: PASS")
                print(f"- {err.split(':')[0]}: FAIL")
                print(f"  Error: {err}")
                print("- Generated model simulation: NOT_RUN")
            else:
                print("- Generated model compilation: PASS")
                print("- Generated model simulation: FAIL")
                print(f"  Error: {err}")
    else:
        print("- Generated model simulation: NOT_RUN (Requires successful LLM generation and Reference simulation)")

    print("\nNumerical Comparison:")
    if ref_sim_result and ref_sim_result.is_success and gen_sim_result and gen_sim_result.is_success:
        num_result = validator.compare_simulations(ref_sim_result, gen_sim_result)
        
        print(f"- Reference LF Gain: {num_result.reference_lf_gain:.4f}")
        print(f"- Generated LF Gain: {num_result.generated_lf_gain:.4f}")
        print(f"- LF Gain Error:     {num_result.lf_gain_error_percent:.4f} %")
        
        print(f"- Reference Cutoff:  {num_result.reference_cutoff_hz:.2f} Hz")
        print(f"- Generated Cutoff:  {num_result.generated_cutoff_hz:.2f} Hz")
        print(f"- Cutoff Error:      {num_result.cutoff_error_percent:.4f} %")
        
        if num_result.is_success:
            print("- Numerical Verification: PASS")
        else:
            print("- Numerical Verification: FAIL")
            for msg in num_result.messages:
                print(f"  Reason: {msg}")
    else:
        print("- Numerical Verification: NOT_RUN")

if __name__ == "__main__":
    main()
