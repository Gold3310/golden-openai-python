from __future__ import annotations

import json
import unittest

import httpx

from examples.reviewed_skill_agent.supabase_audit import SupabaseAuditLogger


class SupabaseAuditLoggerTests(unittest.TestCase):
    def test_insert_uses_user_jwt_publishable_key_and_minimal_payload(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["headers"] = request.headers
            captured["body"] = json.loads(request.content)
            return httpx.Response(201)

        transport = httpx.MockTransport(handler)
        with SupabaseAuditLogger(
            "https://project.supabase.co", "sb_publishable_test", "user-jwt-test", transport=transport
        ) as logger:
            logger.log_event("dependency_audit", "task_started", "started")

        headers = captured["headers"]
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "https://project.supabase.co/rest/v1/agent_audit_events")
        self.assertEqual(headers["apikey"], "sb_publishable_test")
        self.assertEqual(headers["authorization"], "Bearer user-jwt-test")
        self.assertEqual(headers["prefer"], "return=minimal")
        self.assertEqual(
            captured["body"],
            {"skill_name": "dependency_audit", "event_type": "task_started", "status": "started"},
        )

    def test_from_env_is_disabled_when_all_values_are_absent(self) -> None:
        self.assertIsNone(SupabaseAuditLogger.from_env({}))

    def test_from_env_rejects_partial_configuration(self) -> None:
        with self.assertRaises(ValueError):
            SupabaseAuditLogger.from_env({"SUPABASE_URL": "https://project.supabase.co"})

    def test_admin_keys_are_not_a_supported_argument(self) -> None:
        with self.assertRaises(TypeError):
            SupabaseAuditLogger(
                "https://project.supabase.co",
                "sb_publishable_test",
                "user-jwt-test",
                service_role_key="not-supported",
            )

    def test_non_success_response_fails_without_echoing_response_body(self) -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(403, text="sensitive server detail"))
        with SupabaseAuditLogger(
            "https://project.supabase.co", "sb_publishable_test", "user-jwt-test", transport=transport
        ) as logger:
            with self.assertRaisesRegex(RuntimeError, "HTTP 403") as raised:
                logger.log_event("dependency_audit", "task_started", "started")
        self.assertNotIn("sensitive server detail", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
