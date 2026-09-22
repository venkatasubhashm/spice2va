# Spice2VA

Spice2VA is an AI-assisted agent that converts SPICE circuit descriptions into Verilog-A behavioral models and validates them against deterministic physics and SPICE simulation.

## Current Architecture

```text
SPICE netlist
    ↓
SPICE parser
    ↓
Circuit IR
    ↓
Deterministic physics
    ↓
LLM analysis/generation
    ↓
Verilog-A
    ↓
Static validation
    ↓
ngspice reference simulation
    ↓
future: Verilog-A simulation
    ↓
future: numerical comparison
    ↓
future: iterative correction
```

## Current LLM Backend

- **Primary Provider**: Groq
- **Model**: `openai/gpt-oss-120b` (or similar LLM specified by agent configuration)
- **Provider Abstraction**: Implemented generic `LLMProvider` interface.
- **Fallback**: Gemini provider remains available as a fallback.
- **Configuration**: API keys are securely stored in `.env`.

## Current Supported Examples

These represent reference simulation results, NOT generated Verilog-A verification results.

1. **RC low-pass filter**
   - R = 1 kΩ
   - C = 1 µF
   - Expected cutoff ≈ 159.15 Hz
   - ngspice measured ≈ 159.16 Hz
   - Error ≈ 0.01%

2. **Diode circuit**
   - V1 = 1 V
   - R = 1 kΩ
   - Is = 1e-14
   - N = 1
   - ngspice Vd ≈ 0.629441 V
   - Diode current ≈ 0.37056 mA

## Validation Status

- **Structural validation**: implemented
- **Topology validation**: implemented
- **Parameter validation**: implemented
- **Deterministic physics**: implemented
- **ngspice reference simulation**: implemented
- **Deterministic physics vs ngspice comparison**: implemented
- **Generated Verilog-A simulation**: NOT YET AVAILABLE
- **Full Verilog-A numerical verification**: NOT YET IMPLEMENTED
- **Automatic self-correction loop**: NOT YET IMPLEMENTED
- **Datasheet → Verilog-A**: NOT YET IMPLEMENTED
- **Verilog-AMS**: FUTURE

## OpenVAF / Linux Simulation Environment

- Native macOS OpenVAF was investigated.
- Official OpenVAF native macOS/Apple Silicon support is not suitable.
- Colima + Docker was selected as the environment for simulation.
- Docker runs `linux/amd64`.
- OpenVAF 23.5.0 runs successfully inside the container.
- OpenVAF successfully compiled the test Verilog-A model into `.osdi`.
- ngspice 36 is available in the container.
- ngspice currently **FAILS** to instantiate the `.osdi` model.
- Exact current error: `unknown device type`
- Likely cause under investigation:
  - Ubuntu ngspice package may lack OSDI support, and/or
  - `.osdi` loading order in batch mode needs investigation.

*Note: This issue is NOT resolved yet.*

## Environment

### Host
- Apple Silicon Mac M3
- macOS

### Python
- Current project environment uses Python 3.9
- Note: Python 3.9 is EOL and should eventually be upgraded to Python 3.11/3.12.

### LLM
- Groq

### Simulation
- Native macOS ngspice installed (for SPICE reference simulations).
- Linux x86_64 Docker environment through Colima (for Verilog-A simulations).
- OpenVAF 23.5.0
- ngspice 36

## Running Spice2VA

To run the RC low-pass example:
```bash
python3 -m src.main examples/rc_lowpass.cir
```

To run the diode circuit example:
```bash
python3 -m src.main examples/diode.cir
```

## Known Limitations / Next Steps

### Phase 1 — COMPLETE
- parser
- IR
- deterministic physics
- LLM generation
- static validation
- ngspice reference simulation

### Phase 2 — CURRENT
- get OpenVAF + ngspice OSDI simulation working

### Phase 3
- compare generated Verilog-A against SPICE reference
- numerical error metrics
- automatic PASS/FAIL

### Phase 4
- iterative self-correction: generate → simulate → compare → diagnose → regenerate

### Phase 5
- more SPICE devices
- transient analysis
- AC analysis
- nonlinear circuits

### Phase 6
- datasheet/specification → behavioral model

### Phase 7
- Verilog-AMS / mixed-signal modeling
