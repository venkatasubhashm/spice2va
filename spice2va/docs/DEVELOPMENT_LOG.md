# Development Log

This document summarizes the chronological development of the Spice2VA project and the major decisions made during the process.

## 1. Started with SPICE → Verilog-A agent concept
**Why**: The overarching goal is to use AI to automatically generate Verilog-A behavioral models from SPICE netlists to accelerate mixed-signal modeling and ensure behavioral models accurately match SPICE reference circuits.

## 2. Chose not to train a model initially
**Why**: Training or fine-tuning a model requires a large dataset of paired SPICE and Verilog-A models, which is not readily available. Using an off-the-shelf powerful LLM with prompt engineering and a deterministic validation loop is faster to prototype and proves the concept before investing in model training.

## 3. Introduced structured circuit IR (Intermediate Representation)
**Why**: Passing a raw SPICE netlist to an LLM can lead to hallucinations or misinterpretation of topology. Parsing the netlist into a structured JSON/dict format (IR) gives the LLM explicit, disambiguated access to nodes, components, and values, reducing errors.

## 4. Added deterministic physics
**Why**: LLMs are notoriously bad at precise numerical calculations (e.g., cutoff frequencies, bias points). By adding a deterministic physics engine that computes these values structurally, we can cross-verify the LLM's behavioral model parameters and ensure accuracy.

## 5. Added Gemini provider
**Why**: We needed a capable initial LLM provider to process the IR and generate Verilog-A.

## 6. Switched to Groq after Gemini quota issues
**Why**: Encountered rate-limiting and quota restrictions with the Gemini API during rapid iterative development. Switched to Groq (using `openai/gpt-oss-120b` or similar) to maintain development velocity with fast inference and higher limits.

## 7. Added static validation
**Why**: Before simulating the generated Verilog-A, we need to catch obvious syntax errors, missing ports, or incorrect parameters (Structural, Topology, and Parameter validation). This saves time by failing fast before the expensive simulation step.

## 8. Installed native ngspice on macOS
**Why**: We need a ground-truth simulation of the original SPICE netlist to compare against our deterministic physics calculations and the final generated Verilog-A model.

## 9. Added ngspice reference simulation
**Why**: Integrated `NgspiceSimulator` into the pipeline so the agent can automatically run the original `.cir` file in batch mode and extract the reference operating points or AC results.

## 10. Added AC reference validation for RC
**Why**: The RC low-pass filter example required AC analysis to determine the -3dB cutoff frequency. The simulator was enhanced to detect `.ac` directives, run the analysis, and calculate the measured cutoff to compare with the deterministic expected value.

## 11. Added OP reference validation for diode
**Why**: The diode circuit example required nonlinear DC operating point (`.op`) analysis to extract node voltages and device currents. This verified that the deterministic bisection solver accurately matches actual SPICE device models.

## 12. Investigated OpenVAF
**Why**: To validate the *generated* Verilog-A code, we need a Verilog-A compiler. OpenVAF is a modern, open-source compiler that compiles Verilog-A into `.osdi` shared libraries that ngspice can load.

## 13. Determined native macOS OpenVAF was not practical
**Why**: OpenVAF is written in Rust but officially distributes precompiled binaries primarily for Linux. Attempting a native macOS Apple Silicon build involves complex toolchain dependencies (LLVM/Clang) and lacks official support, causing blocking build issues.

## 14. Installed Colima + Docker
**Why**: To run the official `linux/amd64` OpenVAF binary on an Apple Silicon Mac, we needed an x86_64 Linux environment. Colima provides lightweight Linux VMs with Docker support and `rosetta` emulation for AMD64.

## 15. Created isolated linux/amd64 simulation environment
**Why**: Created a minimal `ubuntu:22.04` Docker container with `openvaf` and standard `ngspice` from `apt` to avoid complex source compilation hangs that were occurring during `linux/amd64` emulation on the Mac host.

## 16. Successfully ran OpenVAF 23.5.0
**Why**: Verified that the precompiled binary correctly executes within the emulated Colima Docker container without architecture errors.

## 17. Successfully compiled Verilog-A → `.osdi`
**Why**: After adding `gcc` as a system linker to the Docker image, OpenVAF successfully compiled the test `simple_model.va` into an `.osdi` shared library, validating the compiler toolchain.

## 18. Current blocker: ngspice cannot instantiate the `.osdi` model
**Why**: The standalone pipeline halts because `ngspice` fails with an `unknown device type` error when trying to load the `.osdi` file. This suggests that the standard Ubuntu `ngspice` package may not have been compiled with `--enable-osdi`, or there is a load-order issue in the batch script. This remains the current phase 2 blocker.
