from __future__ import annotations

import os
import json
import base64
from typing import Any, cast
from urllib.parse import urlsplit

import httpx

from .agent import REVIEWED_SKILLS

_ALLOWED_EVENTS = {"task_started", "approval_requested", "approval_decision", "task_completed", "task_failed"}
_ALLOWED_STATUSES = {"started", "pending", "approved", "denied", "completed", "failed"}


def _validate_user_access_token(token: str) -> None:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("SUPABASE_USER_ACCESS_TOKEN must be a Supabase user access JWT.")
    try:
        payload_part = parts[1]
        payload_part += "=" * (-len(payload_part) % 4)
        decoded_claims: object = json.loads(base64.urlsafe_b64decode(payload_part.encode("ascii")))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("SUPABASE_USER_ACCESS_TOKEN must be a validly encoded user JWT.") from None
    if not isinstance(decoded_claims, dict):
        raise ValueError("The Supabase access token must contain a JSON claims object.")
    claims = cast(dict[str, object], decoded_claims)
    if claims.get("role") != "authenticated" or not claims.get("sub"):
        raise ValueError("The Supabase access token must represent an authenticated user, not an administrative role.")


class SupabaseAuditLogger:
    """Insert minimal audit metadata using a user's JWT and RLS; never uses an admin key."""

    def __init__(
        self,
        supabase_url: str,
        publishable_key: str,
        user_access_token: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(supabase_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("SUPABASE_URL must be an HTTPS URL without embedded credentials, query, or fragment.")
        if not publishable_key.startswith("sb_publishable_"):
            raise ValueError("SUPABASE_PUBLISHABLE_KEY must be a Supabase publishable key, not an admin/secret key.")
        if not user_access_token.strip():
            raise ValueError("An authenticated user's access token is required.")
        _validate_user_access_token(user_access_token)
        self._base_url = supabase_url.rstrip("/")
        self._publishable_key = publishable_key
        self._user_access_token = user_access_token
        self._client = httpx.Client(timeout=5.0, follow_redirects=False, transport=transport)

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> SupabaseAuditLogger | None:
        env = os.environ if environ is None else environ
        names = ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_USER_ACCESS_TOKEN")
        values = [env.get(name, "").strip() for name in names]
        if not any(values):
            return None
        if not all(values):
            raise ValueError("Configure all three Supabase audit environment variables or leave all unset.")
        return cls(values[0], values[1], values[2])

    def log_event(self, skill_name: str, event_type: str, status: str) -> None:
        if skill_name not in REVIEWED_SKILLS:
            raise ValueError("Unknown reviewed skill.")
        if event_type not in _ALLOWED_EVENTS or status not in _ALLOWED_STATUSES:
            raise ValueError("Unsupported audit event or status.")

        response = self._client.post(
            f"{self._base_url}/rest/v1/agent_audit_events",
            headers={
                "apikey": self._publishable_key,
                "Authorization": f"Bearer {self._user_access_token}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json={"skill_name": skill_name, "event_type": event_type, "status": status},
        )
        if response.status_code not in (200, 201, 204):
            raise RuntimeError(f"Supabase audit insert failed with HTTP {response.status_code}.")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SupabaseAuditLogger:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
