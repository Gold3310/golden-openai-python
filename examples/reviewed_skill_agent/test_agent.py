from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from examples.reviewed_skill_agent.agent import (
    build_mcp_tool_config,
    build_skill_context,
    continue_after_approval,
    pending_approvals,
    run_developer_agent,
)


class ReviewedSkillAgentTests(unittest.TestCase):
    def test_unknown_skill_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_skill_context("unreviewed")

    def test_dependency_audit_has_only_read_tools_and_approval(self) -> None:
        config = build_mcp_tool_config("dependency_audit", "https://mcp.example.org/mcp")
        self.assertEqual(config["allowed_tools"], ["repo_search", "repo_read_file"])
        self.assertEqual(config["require_approval"], {"always": {"tool_names": ["repo_search", "repo_read_file"]}})

    def test_verified_operation_requires_approval_for_execute_only(self) -> None:
        config = build_mcp_tool_config("verified_operation", "https://mcp.example.org/mcp")
        self.assertEqual(config["allowed_tools"], ["ops_dry_run", "ops_execute", "ops_verify"])
        self.assertEqual(config["require_approval"]["always"]["tool_names"], ["ops_execute"])
        self.assertEqual(config["require_approval"]["never"]["tool_names"], ["ops_dry_run", "ops_verify"])

    def test_invalid_mcp_url_is_rejected(self) -> None:
        for url in ("http://mcp.example.org", "https://user:pass@mcp.example.org", "https://mcp.example.org?token=x"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                build_mcp_tool_config("dependency_audit", url)

    def test_task_is_validated_before_api_call(self) -> None:
        client = Mock()
        with self.assertRaises(ValueError):
            run_developer_agent(client, "dependency_audit", " ", "https://mcp.example.org/mcp")
        client.responses.create.assert_not_called()

    def test_agent_sends_only_reviewed_tools(self) -> None:
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(output_text="audit result", output=[])
        response = run_developer_agent(
            client, "dependency_audit", "Inspect dependency manifests", "https://mcp.example.org/mcp"
        )
        self.assertEqual(response.output_text, "audit result")
        kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(kwargs["tools"][0]["allowed_tools"], ["repo_search", "repo_read_file"])
        self.assertIn("read-only", kwargs["instructions"])

    def test_approval_continuation_sends_explicit_decision(self) -> None:
        client = Mock()
        continue_after_approval(
            client,
            "verified_operation",
            "https://mcp.example.org/mcp",
            "resp_previous",
            "mcpr_pending",
            True,
        )
        kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(kwargs["previous_response_id"], "resp_previous")
        self.assertEqual(kwargs["input"][0]["type"], "mcp_approval_response")
        self.assertTrue(kwargs["input"][0]["approve"])

    def test_pending_approval_output_excludes_arguments(self) -> None:
        response = SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="mcp_approval_request",
                    id="mcpr_pending",
                    name="ops_execute",
                    server_label="engineering",
                    arguments='{"secret":"do-not-print"}',
                )
            ]
        )
        pending = pending_approvals(response)
        self.assertEqual(pending[0]["tool_name"], "ops_execute")
        self.assertNotIn("arguments", pending[0])
        self.assertNotIn("secret", str(pending))


if __name__ == "__main__":
    unittest.main()
