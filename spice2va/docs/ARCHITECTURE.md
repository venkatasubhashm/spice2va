# Spice2VA Architecture

Spice2VA is designed as an agentic pipeline with clearly separated components.

## Architecture Diagram

```text
+---------------------+
|    SPICE Netlist    |
|   (e.g. diode.cir)  |
+---------+-----------+
          |
          v
+---------+-----------+
|       Parser        |  <-- Extracts topology, nodes, parameters
+---------+-----------+
          |
          v
+---------+-----------+
|  Circuit IR (Dict)  |  <-- Structured Intermediate Representation
+---------+-----------+
          |
          +-----------------------------+
          |                             |
          v                             v
+---------+-----------+       +---------+-----------+
|   Physics Engine    |       |   LLM Generator     |
| (Deterministic math)|       | (Groq / gpt-oss)    |
+---------+-----------+       +---------+-----------+
          |                             |
          | (Expected vals)             | (Code generation)
          |                             v
          |                   +---------+-----------+
          |                   | Verilog-A Model     |
          |                   +---------+-----------+
          |                             |
          |                             v
          |                   +---------+-----------+
          |                   | Static Validator    |
          |                   | (Checks IR vs Code) |
          |                   +---------+-----------+
          |                             |
          |                             v
+---------+-----------+       +---------+-----------+
| Reference Simulator |       | Verilog-A Simulator |
| (Native ngspice)    |       | (OpenVAF/ngspice)   | <-- FUTURE
+---------+-----------+       +---------+-----------+
          |                             |
          | (Ref results)               | (Sim results)
          v                             v
+---------+-----------------------------+-----------+
|                  Comparison Engine                | <-- FUTURE
+-------------------------+-------------------------+
                          |
                          v
                +---------+-----------+
                | Iterative Corrector | <-- FUTURE (Regenerates if mismatch)
                +---------------------+
```

## Components

### Parser
Parses standard SPICE netlists (`.cir`) into an Intermediate Representation (IR). It extracts devices, nodes, values, and simulation directives (like `.op` or `.ac`).

### Circuit IR
A structured dictionary/JSON representation of the circuit. This gives the physics engine and LLM an unambiguous view of the topology, preventing hallucinations caused by reading raw SPICE text.

### Physics Engine
A deterministic solver that calculates expected operating points (e.g., diode voltages using bisection) or AC characteristics (e.g., RC cutoff frequency). This provides a reliable ground truth that isn't dependent on LLM capabilities.

### LLM Provider
An abstract interface (`LLMProvider`) that interacts with the language model API. This abstraction allows swapping between Groq, Gemini, or local models without changing the core agent logic.

### Generator
Prompts the LLM with the Circuit IR and generates the behavioral Verilog-A code.

### Validator (Static)
Performs immediate checks on the generated Verilog-A code (Structural, Topology, Parameter validation) against the original Circuit IR to catch gross errors before attempting compilation.

### ngspice Reference Simulator
A backend (`NgspiceSimulator`) that runs the original SPICE netlist through a native ngspice instance. It parses the batch output to provide the true simulated baseline behavior of the circuit.

### Verilog-A Simulator Backend (Future)
An isolated environment (currently via Docker + OpenVAF) that compiles the generated Verilog-A into an `.osdi` library and runs it in ngspice. Backends are intentionally abstracted so we can swap out OpenVAF/ngspice for commercial simulators or Verilog-AMS engines later without redesigning the agent.

### Comparison Engine (Future)
Automatically compares the numerical results of the Reference Simulator against the Verilog-A Simulator and the Deterministic Physics Engine to calculate error margins and determine PASS/FAIL.

### Iterative Agent (Future)
If the Comparison Engine reports a FAIL, this agent diagnoses the error (using the physics engine or LLM) and feeds it back to the Generator to iteratively correct the Verilog-A code until it matches the reference.
