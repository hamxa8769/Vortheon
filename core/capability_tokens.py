"""
LAYER 4: CAPABILITY TOKEN SYSTEM
Ephemeral, cryptographically signed permissions.
Like JWT but for one-time, time-bound, scope-limited actions.
"""

import jwt
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

class CapabilityToken:
    """
    A capability token grants specific permissions for a specific session.

    Structure:
    {
        "sub": "user_id",
        "sid": "session_id", 
        "cap": ["file:read:/docs", "email:draft"],
        "iat": 1234567890,
        "exp": 1234568190,
        "jti": "unique_token_id",
        "tee": "enclave_measurement_hash"
    }

    Signed with platform private key. Verified inside TEE.
    """

    def __init__(self, private_key_pem: str = None):
        if private_key_pem:
            self.private_key = serialization.load_pem_private_key(
                private_key_pem.encode(), password=None
            )
        else:
            # Generate ephemeral key for demo (in production, use HSM)
            self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        self.public_key = self.private_key.public_key()

    def issue_token(
        self,
        user_id: str,
        session_id: str,
        capabilities: List[str],
        ttl_seconds: int = 300,
        tee_measurement: str = None
    ) -> str:
        """Issue a new capability token.

        Args:
            user_id: Subject identity
            session_id: Bound to specific ephemeral session
            capabilities: List like ["file:read:/path", "api:post:endpoint"]
            ttl_seconds: Token lifetime
            tee_measurement: Hash of approved TEE code
        """
        now = datetime.utcnow()

        payload = {
            "sub": user_id,
            "sid": session_id,
            "cap": capabilities,
            "iat": now,
            "exp": now + timedelta(seconds=ttl_seconds),
            "jti": str(uuid.uuid4()),
            "tee": tee_measurement or "mock_tee_v1",
            "iss": "nullai-platform",
            "aud": "nullai-tee"
        }

        token = jwt.encode(payload, self.private_key, algorithm="RS256")
        return token

    def verify_token(self, token: str, required_capability: str = None) -> Dict:
        """Verify token and optionally check specific capability.

        In production, this runs INSIDE the TEE so the platform
        never sees the plaintext capabilities.
        """
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                audience="nullai-tee",
                issuer="nullai-platform"
            )

            if required_capability and required_capability not in payload.get("cap", []):
                raise PermissionError(f"Capability '{required_capability}' not granted")

            return {
                "valid": True,
                "user_id": payload["sub"],
                "session_id": payload["sid"],
                "capabilities": payload["cap"],
                "expires": payload["exp"]
            }

        except jwt.ExpiredSignatureError:
            return {"valid": False, "error": "Token expired"}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def revoke_token(self, token_id: str) -> bool:
        """Revoke a token by ID.

        In ephemeral system: revocation is usually unnecessary
        because tokens expire quickly. But for immediate kills.
        """
        # In production: add to revocation list in Redis (RAM only)
        return True


class PermissionBroker:
    """
    Manages the lifecycle of capability tokens.
    Coordinates between user grants and agent requests.
    """

    def __init__(self):
        self.pending_requests: Dict[str, dict] = {}
        self.active_grants: Dict[str, List[str]] = {}  # session_id -> [tokens]

    def request_permissions(
        self,
        session_id: str,
        agent_id: str,
        requested_caps: List[str]
    ) -> dict:
        """Agent requests permissions. User must approve."""
        request_id = str(uuid.uuid4())

        self.pending_requests[request_id] = {
            "session_id": session_id,
            "agent_id": agent_id,
            "requested": requested_caps,
            "status": "pending",
            "created_at": datetime.utcnow()
        }

        return {
            "request_id": request_id,
            "session_id": session_id,
            "requested_capabilities": requested_caps,
            "approval_url": f"/approve/{request_id}",
            "expires_in": 120  # 2 minutes to approve
        }

    def approve_request(
        self,
        request_id: str,
        token_issuer: CapabilityToken,
        user_id: str,
        approved_caps: List[str] = None
    ) -> dict:
        """User approves permission request."""
        req = self.pending_requests.get(request_id)
        if not req:
            return {"error": "Request not found"}

        # Default: approve all requested
        caps = approved_caps or req["requested"]

        # Issue token
        token = token_issuer.issue_token(
            user_id=user_id,
            session_id=req["session_id"],
            capabilities=caps,
            ttl_seconds=300  # 5 minutes max
        )

        # Track grant
        sid = req["session_id"]
        if sid not in self.active_grants:
            self.active_grants[sid] = []
        self.active_grants[sid].append(token)

        # Clean up request
        del self.pending_requests[request_id]

        return {
            "status": "approved",
            "token": token,
            "capabilities": caps,
            "session_id": sid,
            "expires_in": 300
        }

    def get_session_grants(self, session_id: str) -> List[str]:
        """Get all active capability tokens for a session."""
        return self.active_grants.get(session_id, [])

    def clear_session(self, session_id: str):
        """Clear all grants when session ends."""
        if session_id in self.active_grants:
            del self.active_grants[session_id]
