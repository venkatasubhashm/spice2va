import math
from typing import Dict, Any, Optional
from .ir import Circuit

def analyze_rc_cutoff(circuit: Circuit) -> Optional[float]:
    """
    Deterministically calculates the -3dB cutoff frequency for a simple 1-pole RC filter.
    Returns frequency in Hz, or None if it doesn't look like a simple RC.
    """
    resistors = circuit.get_components_by_type('R')
    capacitors = circuit.get_components_by_type('C')
    
    # For a simple RC circuit, we expect exactly 1 resistor and 1 capacitor
    if len(resistors) != 1 or len(capacitors) != 1:
        return None
        
    r = resistors[0].value
    c = capacitors[0].value
    
    if r is None or c is None or r == 0 or c == 0:
        return None
        
    fc = 1 / (2 * math.pi * r * c)
    tau = r * c
    return {'fc': fc, 'tau': tau}

def analyze_diode(circuit: Circuit) -> Dict[str, Any]:
    """
    Deterministically extracts diode physics and models.
    """
    diodes = circuit.get_components_by_type('D')
    if not diodes:
        return {}
        
    results = {}
    diode = diodes[0]
    
    # Find matching model
    model = next((m for m in circuit.models if m.name == diode.model_name), None)
    
    if model:
        # Defaults if not provided
        is_val = model.params.get('Is', 1e-14)
        n_val = model.params.get('N', 1.0)
        v_t = 0.02585 # Thermal voltage at ~300K
        
        results['diode_equation'] = f"I_D = {is_val} * (exp(V_D / ({n_val} * {v_t})) - 1)"
        results['Is'] = is_val
        results['N'] = n_val
        results['V_T'] = v_t
        
        # Calculate Deterministic DC Operating Point
        # Assuming V1 = 1V and R1 = 1k, f(Vd) = (1 - Vd)/R - Is * (exp(Vd/(N*Vt)) - 1) = 0
        v_source = next((c for c in circuit.components if c.type == 'V'), None)
        r_source = next((c for c in circuit.components if c.type == 'R'), None)
        
        if v_source and r_source and v_source.ac_amplitude is None:
             v_in = v_source.value if v_source.value is not None else 1.0
             r_val = r_source.value if r_source.value is not None else 1000.0
        else:
             # Default fallback values based on the spec
             v_in = 1.0
             r_val = 1000.0
             
        def f(vd):
            # Limiting exp arg to avoid overflow
            exp_arg = min(vd / (n_val * v_t), 100.0) 
            return (v_in - vd) / r_val - is_val * (math.exp(exp_arg) - 1.0)
            
        # Bisection Method (Robust)
        v_low = 0.0
        v_high = v_in
        v_mid = 0.0
        converged = False
        
        if f(v_low) * f(v_high) <= 0:
            for _ in range(100):
                v_mid = (v_low + v_high) / 2.0
                f_mid = f(v_mid)
                
                if abs(f_mid) < 1e-12 or (v_high - v_low) / 2.0 < 1e-12:
                    converged = True
                    break
                    
                if f(v_mid) * f(v_low) > 0:
                    v_low = v_mid
                else:
                    v_high = v_mid
                    
        if converged:
            results['Vd'] = v_mid
            # Limiting exp arg for Id calculation as well
            exp_arg_id = min(v_mid / (n_val * v_t), 100.0)
            results['Id'] = is_val * (math.exp(exp_arg_id) - 1.0)
            results['dc_converged'] = True
        else:
            results['dc_converged'] = False

        results['qualitative_behavior'] = "Nonlinear diode behavior; blocks reverse current, exponential forward current."
        
    return results

def validate_physics(circuit: Circuit) -> Dict[str, Any]:
    """
    Run all deterministic physics validations on the parsed circuit.
    """
    results = {}
    
    # 1. Check for RC cutoff and topology
    rc_results = analyze_rc_cutoff(circuit)
    if rc_results is not None:
        results['rc_cutoff_hz'] = rc_results['fc']
        results['rc_tau'] = rc_results['tau']
        
        # Determine specific topology: RC Low Pass vs High Pass
        resistors = circuit.get_components_by_type('R')
        capacitors = circuit.get_components_by_type('C')
        v_sources = circuit.get_components_by_type('V')
        
        topology = 'Unknown RC'
        if len(v_sources) == 1:
            v_node1, v_node2 = v_sources[0].nodes
            r_node1, r_node2 = resistors[0].nodes
            c_node1, c_node2 = capacitors[0].nodes
            
            # Usually V source is between input and GND (0)
            v_in_nodes = {v_node1, v_node2}
            v_in_nodes.discard('0')
            if len(v_in_nodes) == 1:
                input_node = v_in_nodes.pop()
                
                # Check for RC Low Pass (R between input and out, C between out and GND)
                if input_node in (r_node1, r_node2):
                    r_other = r_node2 if r_node1 == input_node else r_node1
                    if r_other in (c_node1, c_node2):
                        c_other = c_node2 if c_node1 == r_other else c_node1
                        if c_other == '0':
                            topology = 'RC Low Pass'
                            
                # Check for RC High Pass (C between input and out, R between out and GND)
                if input_node in (c_node1, c_node2):
                    c_other = c_node2 if c_node1 == input_node else c_node1
                    if c_other in (r_node1, r_node2):
                        r_other = r_node2 if r_node1 == c_other else r_node1
                        if r_other == '0':
                            topology = 'RC High Pass'

        results['topology_guess'] = topology
        
    # 2. Check for Diode physics
    diode_results = analyze_diode(circuit)
    if diode_results:
        results.update(diode_results)
        
    return results
