FROM --platform=linux/amd64 ubuntu:22.04

# Avoid tzdata interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# Install ngspice, wget, and gcc (for linker)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ngspice \
    gcc \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install official OpenVAF nightly release
RUN wget --timeout 60 https://openva.fra1.digitaloceanspaces.com/openvaf_devel-x86_64-unknown-linux-gnu.tar.gz -O openvaf.tar.gz && \
    tar -xzf openvaf.tar.gz && \
    mv openvaf /usr/local/bin/ && \
    chmod +x /usr/local/bin/openvaf && \
    rm openvaf.tar.gz

WORKDIR /workspace
