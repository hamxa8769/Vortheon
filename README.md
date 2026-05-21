Vortheon
Zero-knowledge AI workforce.
AI agents that process your most sensitive data inside cryptographically sealed environments — then forget everything.
https://opensource.org/licenses/MIT
https://vortheon.ai
https://vortheon.ai
The Problem
Every AI tool today collects, stores, and trains on your data.
Law firms can't use AI for contract review — it leaks to competitors.
Crypto traders can't use AI for analysis — it exposes positions.
Doctors can't use AI for diagnosis — it violates HIPAA.
Vortheon fixes this.
How It Works
plain
Copy
Your Device          Vortheon Platform              AI Model
     │                       │                          │
     ▼                       ▼                          ▼
┌─────────┐          ┌──────────────┐          ┌─────────────┐
│ Encrypt │─────────→│   Ephemeral  │─────────→│  TEE Enclave│
│  (AES)  │   HTTPS  │   Sandbox    │  isolate │  (RAM only) │
└─────────┘          └──────────────┘          └─────────────┘
     ▲                       │                          │
     │                       ▼                          ▼
┌─────────┐          ┌──────────────┐          ┌─────────────┐
│ Decrypt │←─────────│  Auto-Kill   │←─────────│  Inference  │
│ Result  │  HTTPS   │  + Wipe RAM  │  destroy │  (no logs)  │
└─────────┘          └──────────────┘          └─────────────┘
Key guarantees:
✅ Client-side encryption — data is encrypted before leaving your browser
✅ Ephemeral containers — one session = one container, destroyed after use
✅ RAM-only processing — /tmp is tmpfs, no disk writes
✅ Zero logging — API gateway runs with --no-access-log
✅ Capability tokens — permissions expire in minutes, not months
✅ Hardware TEE ready — swap mock TEE for AMD SEV/Intel TDX/AWS Nitro
Quick Start
1. Clone & Install
bash
Copy
git clone https://github.com/YOUR_USERNAME/Vortheon.git
cd Vortheon
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
2. Start Ollama (Local Models)
bash
Copy
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
3. Run the Stack
bash
Copy
# Terminal 1: Redis (RAM-only, no persistence)
docker run -d --name vortheon-redis -p 6379:6379 redis:7-alpine redis-server --save "" --appendonly no

# Terminal 2: API Gateway
uvicorn platform.api_gateway:app --host 0.0.0.0 --port 8000 --no-access-log --reload

# Terminal 3: Inference container
python inference_server.py llama3.2
4. Test It
bash
Copy
curl http://localhost:8000/health
# → {"status": "operational", "logging": "disabled", "data_retention": "zero"}
Architecture
Table
Layer	Component	Purpose
L6	Next.js + WebCrypto	Client-side encryption, trust dashboard
L5	FastAPI Gateway	Zero-log API, token validation
L4	Orchestrator	Spawns/kills ephemeral sandboxes
L3	Docker Runtime	Read-only fs, tmpfs RAM-only, auto-kill
L2	TEE Wrapper	Mock TEE (upgrade path to AMD SEV/Intel TDX)
L1	vLLM / Ollama	Open-source LLM serving
L0	Host	Laptop → Hetzner → AMD EPYC → Cloud TEE
Roadmap
Phase 1: Mock TEE (Now, $0)
[x] Ephemeral container orchestration
[x] Client-side encryption
[x] Capability token system
[ ] Next.js trust dashboard
[ ] First agent: Private Document Analyzer
Phase 2: Soft TEE ($50/mo)
[ ] AMD SEV-SNP on dedicated server
[ ] Kernel-level memory encryption
[ ] First paying customers (law, crypto, medical)
Phase 3: Hard TEE ($250/mo or $1,200 once)
[ ] Hardware attestation (AMD/Intel signatures)
[ ] Remote verification by clients
[ ] Enterprise contracts
Phase 4: Distributed TEE ($2,000+/mo)
[ ] Multi-node TEE across providers
[ ] Byzantine fault tolerance
[ ] Marketplace of privacy-preserving agents
Security Notice
This is a PROTOTYPE. The mock TEE provides zero real security against a compromised host. It demonstrates the architecture and API contract.
For production:
Replace MockTEE with real AMD SEV-SNP / Intel TDX / AWS Nitro Enclaves
Use ECDH key exchange (not mock encryption)
Add memory wipe verification
Get third-party security audit (Trail of Bits, NCC Group)
Mitigate side-channel attacks
License
Core infrastructure: MIT — open source, audit it, trust it.
Platform & marketplace: Proprietary (separate private repo).
Built to prove AI doesn't need to remember you to serve you.
