#!/usr/bin/env python3
"""
INFERENCE SERVER (runs inside ephemeral container)
- Loads model from read-only mount
- Processes requests in RAM only
- Exits on session end (no cleanup needed)
"""

import sys
import os
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

MODEL_NAME = sys.argv[1] if len(sys.argv) > 1 else "llama3.2"
SESSION_ID = os.environ.get("SESSION_ID", "unknown")
EPHEMERAL = os.environ.get("EPHEMERAL_MODE", "0")

class InferenceHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for inference requests."""

    def log_message(self, format, *args):
        # INTENTIONALLY: No access logs in ephemeral mode
        if EPHEMERAL != "1":
            super().log_message(format, *args)

    def do_POST(self):
        if self.path == "/infer":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            # In production: decrypt with session key, run vLLM/Ollama, encrypt result
            # For mock: echo back
            request = json.loads(body)
            prompt = request.get("prompt", "")

            # Simulate inference delay
            time.sleep(0.5)

            response = {
                "result": f"[Enclave {SESSION_ID[:8]}] Processed: {prompt[:100]}",
                "model": MODEL_NAME,
                "session": SESSION_ID,
                "ephemeral": True,
                "memory_only": True
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "alive", "ephemeral": True}).encode())

    def do_GET(self):
        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "model": MODEL_NAME,
                "session": SESSION_ID,
                "uptime": time.time() - START_TIME,
                "memory_only": True,
                "disk_writes": 0
            }).encode())

START_TIME = time.time()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), InferenceHandler)
    print(f"Inference server starting | Model: {MODEL_NAME} | Session: {SESSION_ID} | Port: {port}")
    server.serve_forever()
