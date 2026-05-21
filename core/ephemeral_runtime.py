"""
LAYER 3: EPHEMERAL RUNTIME
Spawns Docker containers that live only for one session.
All data in RAM (tmpfs). No disk writes. Auto-destruction.
"""

import docker
import uuid
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict

class EphemeralSandbox:
    """
    Manages short-lived inference containers.

    Design principles:
    - One session = One container
    - Container has no writable disk (read-only rootfs)
    - /tmp is tmpfs (RAM only, max size limit)
    - Container auto-killed after timeout or disconnect
    - No logs retained (Docker logs are ephemeral by default)
    """

    def __init__(self, image: str = "nullai-inference:latest"):
        self.client = docker.from_env()
        self.image = image
        self.active_sessions: Dict[str, dict] = {}
        self.lock = threading.Lock()

    def spawn_session(
        self, 
        session_id: str = None,
        model_name: str = "llama3.2",
        ram_limit: str = "4g",
        cpu_limit: float = 2.0,
        ttl_seconds: int = 600
    ) -> dict:
        """Spawn a new ephemeral inference container.

        Args:
            session_id: Unique session identifier (auto-generated if None)
            model_name: Which model to load inside container
            ram_limit: Max RAM (e.g., "4g", "8g")
            cpu_limit: Max CPU cores
            ttl_seconds: Time-to-live before auto-kill

        Returns:
            Session metadata with container ID and kill timer
        """
        session_id = session_id or str(uuid.uuid4())

        # Container configuration for zero-persistence
        container_config = {
            "image": self.image,
            "command": ["python", "-u", "/app/inference_server.py", model_name],
            "detach": True,
            "mem_limit": ram_limit,
            "cpu_count": int(cpu_limit),
            "read_only": True,  # CRITICAL: Root filesystem is read-only
            "tmpfs": {
                "/tmp": f"rw,noexec,nosuid,size={ram_limit},mode=1777"
            },
            "network_mode": "none",  # CRITICAL: No network unless explicitly needed
            "environment": {
                "SESSION_ID": session_id,
                "MODEL_NAME": model_name,
                "EPHEMERAL_MODE": "1",
                "NO_PERSISTENCE": "1"
            },
            "labels": {
                "nullai.session": session_id,
                "nullai.ephemeral": "true",
                "nullai.created": datetime.utcnow().isoformat()
            },
            "auto_remove": True,  # CRITICAL: Auto-remove on stop
            "stdin_open": False,
            "tty": False
        }

        try:
            container = self.client.containers.run(**container_config)

            session_data = {
                "session_id": session_id,
                "container_id": container.id,
                "model": model_name,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(seconds=ttl_seconds),
                "status": "running"
            }

            with self.lock:
                self.active_sessions[session_id] = session_data

            # Schedule auto-destruction
            self._schedule_destruction(session_id, ttl_seconds)

            return {
                "session_id": session_id,
                "container_id": container.id[:12],
                "expires_at": session_data["expires_at"].isoformat(),
                "status": "spawned"
            }

        except docker.errors.ImageNotFound:
            return {"error": "Inference image not found. Build it first."}
        except Exception as e:
            return {"error": str(e)}

    def _schedule_destruction(self, session_id: str, delay_seconds: int):
        """Schedule container destruction after TTL."""
        def destroy():
            time.sleep(delay_seconds)
            self.kill_session(session_id, reason="ttl_expired")

        thread = threading.Thread(target=destroy, daemon=True)
        thread.start()

    def kill_session(self, session_id: str, reason: str = "user_request") -> dict:
        """Immediately destroy a session and its container.

        This is the 'memory wipe' operation.
        """
        with self.lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return {"error": "Session not found"}

            try:
                container = self.client.containers.get(session["container_id"])

                # Force kill (SIGKILL) - no graceful shutdown, no cleanup time
                container.kill(signal="SIGKILL")

                # Container auto-removes due to auto_remove=True

                session["status"] = "destroyed"
                session["destroyed_at"] = datetime.utcnow().isoformat()
                session["destroy_reason"] = reason

                # Remove from active sessions
                del self.active_sessions[session_id]

                return {
                    "session_id": session_id,
                    "status": "destroyed",
                    "reason": reason,
                    "memory_wiped": True,
                    "disk_traces": "none (read-only fs + tmpfs)"
                }

            except docker.errors.NotFound:
                del self.active_sessions[session_id]
                return {"error": "Container already gone"}
            except Exception as e:
                return {"error": str(e)}

    def get_session_status(self, session_id: str) -> dict:
        """Get current session status."""
        with self.lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return {"status": "not_found"}

            remaining = (session["expires_at"] - datetime.utcnow()).total_seconds()

            return {
                "session_id": session_id,
                "status": session["status"],
                "model": session["model"],
                "remaining_seconds": max(0, int(remaining)),
                "memory_only": True,
                "disk_persistent": False
            }

    def list_active_sessions(self) -> list:
        """List all active ephemeral sessions."""
        with self.lock:
            return [
                {
                    "session_id": sid,
                    "model": s["model"],
                    "remaining_seconds": max(0, int((s["expires_at"] - datetime.utcnow()).total_seconds()))
                }
                for sid, s in self.active_sessions.items()
            ]


class SandboxMonitor:
    """Background monitor to ensure no containers outlive their TTL."""

    def __init__(self, sandbox: EphemeralSandbox, check_interval: int = 30):
        self.sandbox = sandbox
        self.check_interval = check_interval
        self.running = False

    def start(self):
        """Start monitoring thread."""
        self.running = True
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()

    def _monitor_loop(self):
        while self.running:
            with self.sandbox.lock:
                now = datetime.utcnow()
                expired = [
                    sid for sid, s in self.sandbox.active_sessions.items()
                    if s["expires_at"] < now
                ]

            for sid in expired:
                self.sandbox.kill_session(sid, reason="monitor_cleanup")

            time.sleep(self.check_interval)
