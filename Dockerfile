# NULLAI INFERENCE CONTAINER
# Design: Read-only rootfs, tmpfs for /tmp, no persistent storage

FROM ollama/ollama:latest

# Install Python for the inference bridge
RUN apt-get update && apt-get install -y python3 python3-pip --no-install-recommends     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy inference server (read-only)
COPY inference_server.py /app/inference_server.py
COPY requirements.txt /app/requirements.txt

RUN pip3 install --no-cache-dir -r requirements.txt

# Pre-download model weights (optional - saves startup time)
# RUN ollama pull llama3.2

# CRITICAL SECURITY SETTINGS:
# - Run as non-root
# - Read-only filesystem enforced at runtime
# - No network unless explicitly enabled
# - All temporary data goes to tmpfs (RAM)

USER 1000:1000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=1     CMD python3 -c "print('alive')" || exit 1

ENTRYPOINT ["python3", "-u", "/app/inference_server.py"]
