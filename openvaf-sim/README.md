# OpenVAF Simulator Docker Environment

This is an isolated environment for compiling Verilog-A models using OpenVAF and simulating them with `ngspice`.

## Build
```bash
docker build --platform linux/amd64 -t openvaf-sim .
```

## Verify
```bash
docker run --rm --platform linux/amd64 openvaf-sim openvaf --version
docker run --rm --platform linux/amd64 openvaf-sim ngspice -v
```

## Run Test
```bash
docker run --rm --platform linux/amd64 -v $(pwd)/test:/workspace openvaf-sim bash -c "openvaf simple_model.va && ngspice -b testbench.cir"
```
