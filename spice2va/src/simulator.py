import shutil
import subprocess
import tempfile
import os
import re
import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List

@dataclass
class SimulationResult:
    is_success: bool
    analysis_type: str = "OP"
    results: Dict[str, float] = field(default_factory=dict)
    ac_metrics: Dict[str, float] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""

def _parse_ngspice_op_output(stdout: str) -> Dict[str, float]:
    """
    Isolated regex parser for ngspice .op output.
    Extracts node voltages and branch currents.
    """
    results = {}
    
    # Generic regex for line parsing:
    # ngspice OP output in batch mode usually has lines like:
    #  v1#branch   -0.001000
    #  in          1.000000
    
    lines = stdout.split('\n')
    for line in lines:
        line = line.strip()
        # Skip empty lines, separators, and known headers
        if not line or line.startswith('-') or line.lower().startswith('node') or line.lower().startswith('source'):
            continue
            
        parts = line.split()
        if len(parts) == 2:
            key = parts[0].lower()
            val_str = parts[1]
            try:
                val = float(val_str)
                results[key] = val
            except ValueError:
                pass
                
    return results

def _parse_ngspice_ac_output(stdout: str) -> Dict[str, float]:
    """
    Parses ngspice AC output to extract low-frequency gain and -3dB cutoff.
    """
    metrics = {}
    
    # Extract data points: (freq, mag)
    data_points: List[Tuple[float, float]] = []
    
    lines = stdout.split('\n')
    parsing_table = False
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('-'):
            continue
            
        if line.startswith('Index') and 'frequency' in line.lower():
            parsing_table = True
            continue
            
        if parsing_table:
            parts = line.split()
            # AC table has index, freq, vm(out), maybe vp(out)
            if len(parts) >= 3:
                try:
                    # parts[0] is index, parts[1] is freq, parts[2] is vm(out)
                    freq = float(parts[1])
                    mag = float(parts[2])
                    data_points.append((freq, mag))
                except ValueError:
                    pass
                    
    if not data_points:
        return metrics
        
    # Low frequency gain is the magnitude at the lowest simulated frequency
    lf_gain = data_points[0][1]
    metrics['lf_gain'] = lf_gain
    
    # Find -3dB cutoff (mag drops below lf_gain / sqrt(2))
    target_mag = lf_gain / math.sqrt(2.0)
    cutoff_freq = None
    
    for i in range(1, len(data_points)):
        freq_prev, mag_prev = data_points[i-1]
        freq_curr, mag_curr = data_points[i]
        
        if mag_curr <= target_mag <= mag_prev:
            # Linear interpolation for better precision
            # (target_mag - mag_prev) / (mag_curr - mag_prev) = (cutoff_freq - freq_prev) / (freq_curr - freq_prev)
            if mag_curr != mag_prev:
                ratio = (target_mag - mag_prev) / (mag_curr - mag_prev)
                cutoff_freq = freq_prev + ratio * (freq_curr - freq_prev)
            else:
                cutoff_freq = freq_curr
            break
            
    if cutoff_freq is not None:
        metrics['cutoff_hz'] = cutoff_freq
        
    return metrics

class NgspiceSimulator:
    def get_ngspice_path(self) -> str:
        return os.environ.get("NGSPICE_PATH", "ngspice")
        
    def get_openvaf_path(self) -> str:
        return os.environ.get("OPENVAF_PATH", "openvaf")

    def is_available(self) -> bool:
        return shutil.which(self.get_ngspice_path()) is not None
        
    def run_reference(self, netlist_path: str) -> SimulationResult:
        """
        Runs ngspice in batch mode on a copy of the netlist.
        """
        if not self.is_available():
            return SimulationResult(is_success=False, stderr="ngspice not found in PATH")
            
        abs_path = os.path.abspath(netlist_path)
        if not os.path.exists(abs_path):
             return SimulationResult(is_success=False, stderr=f"Netlist not found: {abs_path}")
             
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_netlist = os.path.join(temp_dir, "circuit.cir")
            
            # Check for AC analysis and inject .print if necessary
            is_ac = False
            with open(abs_path, 'r') as f:
                lines = f.readlines()
                
            for line in lines:
                if line.strip().lower().startswith('.ac '):
                    is_ac = True
                    break
                    
            with open(temp_netlist, 'w') as f:
                for line in lines:
                    if line.strip().lower().startswith('.end') and is_ac:
                        # Inject print statement before .end
                        f.write(".print ac vm(out)\n")
                    f.write(line)
            
            try:
                process = subprocess.run(
                    [self.get_ngspice_path(), "-b", "circuit.cir"],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                is_success = process.returncode == 0
                
                if is_ac:
                    ac_metrics = _parse_ngspice_ac_output(process.stdout)
                    return SimulationResult(
                        is_success=is_success,
                        analysis_type="AC",
                        ac_metrics=ac_metrics,
                        stdout=process.stdout,
                        stderr=process.stderr
                    )
                else:
                    results = _parse_ngspice_op_output(process.stdout)
                    return SimulationResult(
                        is_success=is_success,
                        analysis_type="OP",
                        results=results,
                        stdout=process.stdout,
                        stderr=process.stderr
                    )
                    
            except Exception as e:
                return SimulationResult(is_success=False, stderr=str(e))

    def _extract_module_interface(self, va_path: str) -> tuple:
        with open(va_path, "r") as f:
            code = f.read()
            
        mod_match = re.search(r"module\s+(\w+)\s*\((.*?)\);", code)
        if not mod_match:
            return None, None, None, "Module declaration not found"
            
        mod_name = mod_match.group(1)
        ports = [p.strip() for p in mod_match.group(2).split(",")]
        
        # Extract parameters
        params = []
        param_matches = re.finditer(r"parameter\s+(?:real|integer)\s+(\w+)", code)
        for pm in param_matches:
            params.append(pm.group(1))
            
        return mod_name, ports, params, None

    def run_generated_model(self, va_path: str, circuit) -> SimulationResult:
        import shutil
        import subprocess
        import tempfile
        import os
        
        if not shutil.which(self.get_openvaf_path()):
             return SimulationResult(is_success=False, stderr="OpenVAF Compilation Failed: OpenVAF not found in PATH")
             
        abs_va_path = os.path.abspath(va_path)
        if not os.path.exists(abs_va_path):
             return SimulationResult(is_success=False, stderr=f"Generated Verilog-A not found: {abs_va_path}")
             
        mod_name, ports, params, err = self._extract_module_interface(abs_va_path)
        if err:
             return SimulationResult(is_success=False, stderr=f"Port Mapping Failed: {err}")
             
        with tempfile.TemporaryDirectory() as temp_dir:
            osdi_path = os.path.join(temp_dir, f"{mod_name}.osdi")
            
            # Compile OpenVAF
            try:
                compile_proc = subprocess.run(
                    [self.get_openvaf_path(), abs_va_path, "-o", osdi_path],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if compile_proc.returncode != 0:
                     return SimulationResult(is_success=False, stderr=f"OpenVAF Compilation Failed:\n{compile_proc.stderr}")
            except Exception as e:
                 return SimulationResult(is_success=False, stderr=f"OpenVAF Compilation Failed: {str(e)}")
                 
            # Parameter Mapping
            param_str_parts = []
            for p in params:
                matched_val = None
                for comp in circuit.components:
                    if comp.type.lower() == p.lower() and comp.value is not None:
                        matched_val = comp.value
                        break
                if matched_val is not None:
                    param_str_parts.append(f"{p}={matched_val}")
                else:
                    return SimulationResult(is_success=False, stderr=f"Parameter Mapping Failed: Could not find value for parameter {p}")
            
            param_str = " ".join(param_str_parts)
            
            # Port Mapping
            valid_nodes = set()
            for c in circuit.components:
                for n in c.nodes:
                    if n != '0':
                        valid_nodes.add(n)
            
            if set(ports) != valid_nodes:
                return SimulationResult(is_success=False, stderr=f"Port Mapping Failed: Generated ports {ports} do not match circuit nodes {list(valid_nodes)}")
                
            mapped_nodes = []
            for port in ports:
                mapped_nodes.append(port)
                
            node_str = " ".join(mapped_nodes)
            
            # Extract AC directive and V stimulus from circuit
            ac_directive = next((d for d in circuit.directives if d.type.lower() == "ac"), None)
            v_stimulus = next((c for c in circuit.components if c.type.lower() == "v"), None)
            
            if not ac_directive or not v_stimulus:
                 return SimulationResult(is_success=False, stderr="Generated Model Simulation Failed: Missing AC directive or V stimulus in reference circuit")
                 
            tb_lines = []
            tb_lines.append(f"Testbench for {mod_name}")
            
            v_nodes = " ".join(v_stimulus.nodes)
            tb_lines.append(f"{v_stimulus.name} {v_nodes} DC 0 AC {v_stimulus.ac_amplitude if v_stimulus.ac_amplitude else 1.0}")
            
            tb_lines.append(f"N1 {node_str} {mod_name}_model")
            if param_str:
                tb_lines.append(f".model {mod_name}_model {mod_name} ({param_str})")
            else:
                tb_lines.append(f".model {mod_name}_model {mod_name}")
            
            tb_lines.append(".control")
            tb_lines.append(f"pre_osdi {osdi_path}")
            ac_params = " ".join(ac_directive.params)
            tb_lines.append(f"ac {ac_params}")
            tb_lines.append("print vm(out)")
            tb_lines.append("quit")
            tb_lines.append(".endc")
            tb_lines.append(".end")
            
            testbench_content = "\n".join(tb_lines)
            
            temp_netlist = os.path.join(temp_dir, "testbench.cir")
            with open(temp_netlist, "w") as f:
                f.write(testbench_content)
                
            try:
                process = subprocess.run(
                    [self.get_ngspice_path(), "-b", "testbench.cir"],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                is_success = process.returncode == 0
                if "fatal error" in process.stdout.lower() or "no such command available" in process.stdout.lower():
                    is_success = False
                    
                if not is_success:
                    return SimulationResult(is_success=False, stderr=f"Generated Model Simulation Failed:\n{process.stdout}\n{process.stderr}")
                    
                ac_metrics = _parse_ngspice_ac_output(process.stdout)
                return SimulationResult(
                    is_success=True,
                    analysis_type="AC",
                    ac_metrics=ac_metrics,
                    stdout=process.stdout,
                    stderr=process.stderr
                )
                    
            except Exception as e:
                return SimulationResult(is_success=False, stderr=f"Generated Model Simulation Failed: {str(e)}")
