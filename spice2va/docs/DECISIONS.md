# Decision Log

This document records the major architectural and design decisions for Spice2VA.

## Why SPICE netlists first?
SPICE is the universal lingua franca of analog circuit design. Starting with SPICE netlists (rather than schematics or datasheets) provides a structured, unambiguous, and easily parsable input that is strictly tied to numerical simulation.

## Why Verilog-A before Verilog-AMS?
Verilog-A focuses purely on continuous-time analog behavior, which directly maps to SPICE primitives. Verilog-AMS introduces discrete-time event-driven semantics and mixed-signal boundary complexities that make generation and validation significantly harder for an initial AI agent.

## Why structured IR?
LLMs are prone to hallucinating connections or misinterpreting text-based netlists. Parsing SPICE into a structured Intermediate Representation (JSON/Dict) explicitly defines nodes, terminals, and parameters, ensuring the LLM focuses on generating the physics/math rather than guessing the topology.

## Why deterministic physics alongside LLM?
LLMs (even the most capable ones) are unreliable at performing precise floating-point arithmetic or complex physics calculations (like nonlinear bisection). By embedding a deterministic physics engine, we can compute the *exact* expected outcomes and compare them against the LLM-generated code, ensuring reliability.

## Why provider abstraction?
The landscape of LLMs moves rapidly. Hardcoding to OpenAI, Gemini, or Groq limits the agent. The `LLMProvider` interface allows us to swap models dynamically based on cost, context limits, or performance.

## Why Groq?
Groq provides extremely low-latency inference for large models (e.g., `gpt-oss-120b`). This was chosen after hitting API quota and rate limits with Gemini during the rapid iterative generation loops required by the agent.

## Why ngspice as reference?
ngspice is open-source, highly compliant with standard SPICE, scriptable via batch mode, and readily available across OS platforms. It serves as an excellent ground-truth simulator for generating reference data.

## Why Docker/Colima?
To validate the generated Verilog-A code, we require a Verilog-A compiler like OpenVAF. However, building OpenVAF natively on macOS (especially Apple Silicon) involves complex Rust/LLVM cross-compilation toolchains. A `linux/amd64` Docker container running through Colima provides an isolated, reproducible environment that natively supports the official OpenVAF binaries.

## Why not native OpenVAF on macOS?
Native compilation attempts on Apple Silicon were abandoned due to blocking issues with the embedded LLVM build and a lack of official support/precompiled binaries from the OpenVAF maintainers for `aarch64-apple-darwin`.

## Why not train/fine-tune yet?
Training a model from scratch or fine-tuning requires a massive, high-quality dataset of paired SPICE netlists and Verilog-A code. Creating an agentic workflow with prompt engineering, static validation, and deterministic simulation is a faster way to prove the concept and can eventually be used to *synthesize* the dataset required for future fine-tuning.
