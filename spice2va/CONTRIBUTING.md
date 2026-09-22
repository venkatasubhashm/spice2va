# Contributor Overview

Welcome to **Spice2VA**! If you are a new contributor, this document will give you a high-level overview of the project's goals, our current progress, the architecture, and where you can jump in to help.

## The Vision
Spice2VA is an AI-assisted agent designed to automatically convert standard SPICE circuit descriptions (`.cir`) into Verilog-A behavioral models. 

Instead of relying purely on a Language Model (which can hallucinate math and topology), Spice2VA pairs an LLM with a **Deterministic Physics Engine**. The physics engine grounds the model by providing exact expected values (like cutoff frequencies or diode voltages), and a native reference simulator (ngspice) provides ground-truth behavior.

Our ultimate goal is an iterative, self-correcting agent that can generate, simulate, compare, and fix mixed-signal models autonomously.

## What is Working Today (Phase 1 Complete)
We have successfully built the foundation of the agent pipeline:
- **SPICE Parsing & IR**: Netlists are reliably parsed into a structured Intermediate Representation (IR).
- **Deterministic Physics**: We can mathematically solve for expected AC/DC behaviors (e.g., RC filters, diode bisection).
- **LLM Generation**: The generic `LLMProvider` (currently using Groq for speed) successfully generates Verilog-A code based on the IR.
- **Static Validation**: The system catches gross structural/parameter errors in the generated Verilog-A before simulation.
- **Reference Simulation**: We automatically run the original `.cir` files through native `ngspice` to extract baseline measurements.

## What is in Progress (Phase 2 Blockers)
We are currently building the Verilog-A simulation backend to test the *generated* models. 
- We are using **OpenVAF** to compile Verilog-A into `.osdi` libraries, running inside an isolated `linux/amd64` Docker environment.
- **Current Blocker:** OpenVAF successfully compiles the `.osdi` file, but our containerized `ngspice` is failing to load it (`unknown device type` error). Resolving this is the immediate priority.

## The Architecture at a Glance
Spice2VA is strictly modular. The core pipeline is:
`SPICE -> Parser -> IR -> Physics/LLM -> Verilog-A -> Validator -> Simulation -> (Future) Iterative Correction`

For a detailed breakdown of the components, please read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
To understand *why* we made certain technical choices (like SPICE first, or Groq over Gemini), read [`docs/DECISIONS.md`](docs/DECISIONS.md).
For a timeline of how the project evolved to this point, check [`docs/DEVELOPMENT_LOG.md`](docs/DEVELOPMENT_LOG.md).

## Technology Stack
- **Language**: Python 3.9 (Plan to migrate to 3.11+)
- **LLM**: Groq API (`openai/gpt-oss-120b`)
- **Reference Simulator**: `ngspice` (Native macOS)
- **Verilog-A Compiler**: OpenVAF 23.5.0 (Running in `linux/amd64` Docker via Colima)

## Where We Need Help (The Roadmap)
If you're looking to contribute, here is what's coming next:
1. **Fixing the OSDI Loader**: Get `ngspice` in Docker to successfully load and simulate the OpenVAF `.osdi` files.
2. **Comparison Engine**: Build the logic to automatically compare the reference SPICE results against the generated Verilog-A results and compute error margins.
3. **Iterative Self-Correction**: Close the loop! Feed failures back into the LLM with diagnostic context to regenerate the Verilog-A until it passes.
4. **Expanding Device Support**: Move beyond resistors, capacitors, and diodes into nonlinear devices, transistors, and complex subcircuits.

Thank you for contributing to Spice2VA! We are excited to have you on board.
