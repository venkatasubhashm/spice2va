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
    def is_available(self) -> bool:
        return shutil.which("ngspice") is not None
        
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
                    ["ngspice", "-b", "circuit.cir"],
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
