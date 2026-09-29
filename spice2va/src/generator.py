import os
from typing import Dict, Any
from .llm.gemini import VerilogAModelOutput
from .validator import ValidationReport

class Generator:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def save(self, basename: str, model_output: VerilogAModelOutput, phys_results: Dict[str, Any], validation: ValidationReport) -> str:
        """
        Validates and saves the Verilog-A code and markdown report.
        Returns the path to the Verilog-A file.
        """
        # 1. Save Verilog-A
        va_path = os.path.join(self.output_dir, f"{basename}.va")
        
        va_content = model_output.verilog_a_code.strip()
        
        # 1. Iteratively un-escape JSON string if the LLM double/triple-encoded it
        while va_content.startswith('"') and va_content.endswith('"'):
            import json
            try:
                decoded = json.loads(va_content)
                if isinstance(decoded, str):
                    va_content = decoded.strip()
                else:
                    break
            except Exception:
                break
                
        # 2. Extract from Markdown code block if the LLM wrapped it
        if va_content.startswith('```'):
            lines = va_content.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith('```'):
                lines = lines[:-1]
            va_content = '\n'.join(lines).strip()
            
        # 3. Handle raw escaped string that lacks outer quotes
        # (Groq sometimes outputs literal \n and \" without outer quotes)
        # We only attempt this if there are NO actual newlines, minimizing false positives.
        if '\\n' in va_content and '\n' not in va_content:
            import json
            try:
                decoded = json.loads(f'"{va_content}"')
                if isinstance(decoded, str):
                    va_content = decoded.strip()
            except Exception:
                pass
            
        if validation.overall == "FAIL":
            va_content = "// WARNING: Validation failed. See analysis report.\n" + va_content
            
        with open(va_path, "w") as f:
            f.write(va_content)
            
        # 2. Save Markdown Report
        md_path = os.path.join(self.output_dir, f"{basename}_analysis.md")
        with open(md_path, "w") as f:
            f.write(f"# Circuit Analysis: {basename}\n\n")
            f.write(f"## Summary\n{model_output.circuit_summary}\n\n")
            f.write(f"## Topology\n{model_output.topology}\n\n")
            f.write(f"## Equations\n{model_output.equations}\n\n")
            f.write(f"## Assumptions\n{model_output.assumptions}\n\n")
            f.write(f"## Expected Behavior\n{model_output.expected_behavior}\n\n")
            f.write(f"## Validation Plan\n{model_output.validation_plan}\n\n")
            
            f.write("## Deterministic Reference\n")
            if 'rc_cutoff_hz' in phys_results:
                f.write("### RC\n")
                f.write(f"fc = {phys_results['rc_cutoff_hz']:.2f} Hz\n")
                f.write(f"tau = {phys_results['rc_tau']:.6g} s\n\n")
            
            if 'Vd' in phys_results:
                f.write("### Diode\n")
                f.write(f"Vd = {phys_results['Vd']:.4f} V\n")
                f.write(f"Id = {phys_results['Id']:.6g} A\n\n")
                
            f.write("## Generated Model Checks\n")
            f.write(f"Structural: {validation.structural}\n")
            f.write(f"Topology: {validation.topology}\n")
            f.write(f"Parameters: {validation.parameters}\n")
            f.write(f"Physics: {validation.physics}\n")
            f.write(f"Abstraction: {validation.abstraction}\n\n")
            
            if validation.messages:
                f.write("### Validation Messages\n")
                for msg in validation.messages:
                    f.write(f"- {msg}\n")
                f.write("\n")
                
            f.write("## Overall Result\n")
            f.write(f"{validation.overall}\n")
            
        return va_path
