import re
from typing import Optional
from .ir import Circuit, Component, Directive, SpiceModel

def parse_value(value_str: str) -> Optional[float]:
    """Parse SPICE values like 1k, 1u, 100M into float."""
    multipliers = {
        'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6,
        'm': 1e-3, 'k': 1e3, 'meg': 1e6, 'g': 1e9, 't': 1e12
    }
    
    # Clean string
    val = value_str.lower().strip()
    
    # Match number and optional unit/multiplier
    match = re.match(r"^([+-]?\d*\.?\d+(?:e[+-]?\d+)?)\s*([a-z]*)$", val)
    if not match:
        return None
        
    num_part = float(match.group(1))
    unit_part = match.group(2)
    
    if not unit_part:
        return num_part
        
    # Check for multiplier at the start of the unit part
    for mult, factor in multipliers.items():
        if unit_part.startswith(mult):
            return num_part * factor
            
    return num_part

class SpiceParser:
    def __init__(self):
        pass
        
    def parse(self, netlist: str) -> Circuit:
        circuit = Circuit()
        lines = [line.strip() for line in netlist.split('\n') if line.strip()]
        
        # Assume first line is title if it doesn't start with * or . or letter
        if lines and not lines[0].startswith(('*', '.')) and lines[0][0].isalpha() is False:
             circuit.title = lines[0]
        elif lines and lines[0].startswith('*'):
             circuit.title = lines[0].lstrip('*').strip()

        for line in lines:
            if not line or line.startswith('*'):
                continue
                
            if line.startswith('.model'):
                # e.g., .model Dmod D(Is=1e-14 N=1)
                match = re.match(r"^\.model\s+(\S+)\s+(\S+)\s*\((.*)\)$", line, re.IGNORECASE)
                if match:
                    m_name = match.group(1)
                    m_type = match.group(2).upper()
                    m_params_str = match.group(3)
                    
                    params = {}
                    # Extract Key=Value pairs
                    for p_match in re.finditer(r"([a-zA-Z0-9_]+)\s*=\s*([0-9eE\.\+\-]+)", m_params_str):
                        key = p_match.group(1)
                        val = parse_value(p_match.group(2))
                        if val is not None:
                            params[key] = val
                            
                    circuit.models.append(SpiceModel(name=m_name, model_type=m_type, params=params))
                continue

            if line.startswith('.'):
                parts = line.split()
                circuit.directives.append(Directive(type=parts[0][1:].lower(), params=parts[1:]))
                continue
                
            # Component parsing (very basic, R/C/L/V/I)
            parts = line.split()
            if len(parts) >= 4:
                name = parts[0]
                comp_type = name[0].upper()
                
                # V and I can have more complex arguments (e.g., AC 1), just grab nodes and remaining string
                if comp_type in ('V', 'I'):
                    nodes = parts[1:3]
                    val_str = " ".join(parts[3:])
                    val = None # Don't parse complex source values to float for now
                    ac_amp = None
                    
                    # Very basic AC amplitude parsing
                    if 'AC' in [p.upper() for p in parts]:
                        ac_idx = [p.upper() for p in parts].index('AC')
                        if ac_idx + 1 < len(parts):
                            ac_amp = parse_value(parts[ac_idx + 1])
                            
                    circuit.components.append(Component(
                        name=name,
                        type=comp_type,
                        nodes=nodes,
                        value_str=val_str,
                        value=val,
                        ac_amplitude=ac_amp
                    ))
                elif comp_type == 'D':
                    nodes = parts[1:3]
                    model_name = parts[3]
                    circuit.components.append(Component(
                        name=name,
                        type=comp_type,
                        nodes=nodes,
                        value_str=model_name,
                        model_name=model_name
                    ))
                else:
                    nodes = parts[1:3]
                    val_str = parts[3]
                    val = parse_value(val_str)
                    
                    circuit.components.append(Component(
                        name=name,
                        type=comp_type,
                        nodes=nodes,
                        value_str=val_str,
                        value=val
                    ))
                
        return circuit
