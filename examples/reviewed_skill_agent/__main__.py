from __future__ import annotations

import argparse
import os

from openai import OpenAI

from .agent import pending_approvals, run_developer_agent
from .supabase_audit import SupabaseAuditLogger


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a reviewed-skill developer agent.")
    parser.add_argument("--skill", required=True, choices=("dependency_audit", "verified_operation"))
    parser.add_argument("--task", required=True, help="Task text; do not include credentials or secrets.")
    args = parser.parse_args()

    server_url = os.environ.get("MCP_SERVER_URL", "").strip()
    if not server_url:
        parser.error("MCP_SERVER_URL must point to your reviewed HTTPS MCP server.")

    audit = SupabaseAuditLogger.from_env()
    if audit is not None:
        audit.log_event(args.skill, "task_started", "started")

    try:
        client = OpenAI()
        response = run_developer_agent(
            client=client,
            skill_name=args.skill,
            user_task=args.task,
            server_url=server_url,
            model=os.environ.get("OPENAI_MODEL", "gpt-6-astra"),
        )
        if response.output_text:
            print(response.output_text)
        approvals = pending_approvals(response)
        for approval in approvals:
            print(
                "MCP approval pending: "
                f"tool={approval['tool_name']} "
                f"approval_request_id={approval['approval_request_id']} "
                f"server={approval['server_label']}"
            )
        if audit is not None:
            if approvals:
                audit.log_event(args.skill, "approval_requested", "pending")
            elif getattr(response, "status", "completed") == "completed":
                audit.log_event(args.skill, "task_completed", "completed")
            else:
                audit.log_event(args.skill, "task_failed", "failed")
        return 0 if approvals or getattr(response, "status", "completed") == "completed" else 1
    except Exception:
        if audit is not None:
            audit.log_event(args.skill, "task_failed", "failed")
        raise
    finally:
        if audit is not None:
            audit.close()


if __name__ == "__main__":
    raise SystemExit(main())
