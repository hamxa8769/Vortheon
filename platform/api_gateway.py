"""
LAYER 5: API GATEWAY
FastAPI server with zero logging, token validation, and ephemeral orchestration.
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

from core.tee_wrapper import MockTEE
from core.ephemeral_runtime import EphemeralSandbox
from core.capability_tokens import CapabilityToken, PermissionBroker

app = FastAPI(
    title="NullAI Core",
    description="Zero-knowledge AI inference gateway",
    version="0.1.0"
)

# CORS for local dev (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances (in production, use dependency injection)
sandbox = EphemeralSandbox()
token_issuer = CapabilityToken()
broker = PermissionBroker()

# INTENTIONALLY: No request logging middleware
# INTENTIONALLY: No database connections
# INTENTIONALLY: All state is ephemeral

class InferenceRequest(BaseModel):
    encrypted_prompt: str
    nonce: str
    session_id: str
    capability_token: str

class PermissionRequest(BaseModel):
    session_id: str
    agent_id: str
    capabilities: List[str]

class PermissionApproval(BaseModel):
    request_id: str
    user_id: str
    approved_capabilities: Optional[List[str]] = None


@app.post("/session/spawn")
async def spawn_session(
    model: str = "llama3.2",
    ram: str = "4g",
    ttl: int = 600
):
    """Spawn a new ephemeral inference session."""
    result = sandbox.spawn_session(
        model_name=model,
        ram_limit=ram,
        ttl_seconds=ttl
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result

@app.post("/session/{session_id}/kill")
async def kill_session(session_id: str):
    """Immediately destroy a session. Memory wiped."""
    result = sandbox.kill_session(session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.get("/session/{session_id}/status")
async def session_status(session_id: str):
    """Check session status and remaining lifetime."""
    return sandbox.get_session_status(session_id)

@app.post("/permissions/request")
async def request_permissions(req: PermissionRequest):
    """Agent requests permissions for a session."""
    return broker.request_permissions(
        session_id=req.session_id,
        agent_id=req.agent_id,
        requested_caps=req.capabilities
    )

@app.post("/permissions/approve")
async def approve_permissions(req: PermissionApproval):
    """User approves permission request."""
    return broker.approve_request(
        request_id=req.request_id,
        token_issuer=token_issuer,
        user_id=req.user_id,
        approved_caps=req.approved_capabilities
    )

@app.post("/inference")
async def inference(req: InferenceRequest):
    """
    Process encrypted inference request.

    Flow:
    1. Verify capability token
    2. Verify session exists and is active
    3. Route to TEE container
    4. Return encrypted result
    """
    # Verify token
    token_check = token_issuer.verify_token(
        req.capability_token, 
        required_capability="inference:run"
    )

    if not token_check.get("valid"):
        raise HTTPException(status_code=403, detail="Invalid capability token")

    # Verify session
    session = sandbox.get_session_status(req.session_id)
    if session["status"] != "running":
        raise HTTPException(status_code=400, detail="Session not active")

    # In production: forward to actual TEE container
    # For mock: simulate processing
    tee = MockTEE(enclave_id=req.session_id)

    # This would be real ECDH in production
    result = tee.process_encrypted_input(req.encrypted_prompt, req.nonce)

    return {
        "session_id": req.session_id,
        "encrypted_result": result["ciphertext"],
        "result_nonce": result["nonce"],
        "processed_in_enclave": True,
        "no_logs_retained": True
    }

@app.get("/attestation/{session_id}")
async def get_attestation(session_id: str):
    """Get TEE attestation for a session."""
    tee = MockTEE(enclave_id=session_id)
    return tee.generate_attestation()

@app.get("/health")
async def health():
    """Health check. No sensitive data."""
    return {
        "status": "operational",
        "ephemeral_mode": True,
        "logging": "disabled",
        "data_retention": "zero"
    }

if __name__ == "__main__":
    # Run with no access logs (add --no-access-log in production)
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
