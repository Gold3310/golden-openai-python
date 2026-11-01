# Reviewed-skill developer agent

This is an isolated example application inside the `Gold3310/golden-openai-python` fork. It does not change the SDK's generated client implementation.

## Security model

- Skills are an allowlist. Unknown skills fail closed.
- The Responses API MCP configuration exposes only the tool names listed for the selected skill.
- `dependency_audit` exposes `repo_search` and `repo_read_file` only. Both require approval before the remote MCP server receives a call.
- `verified_operation` exposes `ops_dry_run`, `ops_execute`, and `ops_verify`. Only `ops_execute` is configured to require explicit approval; dry run and verification are the only approval-exempt tools.
- The remote MCP server must independently enforce authorization, operation bounds, idempotency, retry limits, and verification. Model instructions and client-side allowlists are not a substitute for server-side authorization.
- Repository content and tool output are untrusted input. Never pass private keys, seed phrases, passwords, API keys, access tokens, or other secrets in task text.

OpenAI's Responses API supports MCP tool allowlists and per-tool approval policies. An approval request is returned as an `mcp_approval_request`; the application must review it and send an explicit `mcp_approval_response` before the tool call proceeds.

## Configuration

Use environment variables; do not commit a populated environment file:

- `OPENAI_API_KEY`: OpenAI API key.
- `OPENAI_MODEL`: optional model override; defaults to `gpt-6-astra`.
- `MCP_SERVER_URL`: HTTPS URL of the reviewed MCP server. The endpoint must expose the tool names above.
- `SUPABASE_URL`: Supabase project URL (optional; configure all three Supabase values together).
- `SUPABASE_PUBLISHABLE_KEY`: Supabase publishable key, not a secret key.
- `SUPABASE_USER_ACCESS_TOKEN`: current access JWT for the signed-in user. The client rejects tokens whose unverified claims do not identify the `authenticated` role; Supabase still validates the token signature and expiry. Never use a service-role or secret key here.

Run from the repository root:

```sh
python -m examples.reviewed_skill_agent --skill dependency_audit --task "Check the repository for exposure to the supplied advisory. Stay read-only."
```

The CLI prints response text and the tool name plus approval request ID for pending approvals. It intentionally does not print tool arguments. **This CLI does not approve requests.** A production host application must retrieve the pending request from the trusted response object, render its complete arguments in a secure review surface with secret redaction, bind the reviewer decision to that exact request, and only then call `continue_after_approval(...)` with the corresponding record from `pending_approvals(response)`. The helper rejects approval records for tools outside the selected skill's approval-required list and for unexpected server labels. Denials use `approved=False`. The helper writes the decision to the audit table only after the Responses API accepts the decision.

## Supabase audit persistence

The optional logger writes only `skill_name`, `event_type`, and `status`. These user-writable rows are operational telemetry, not a tamper-proof compliance audit trail. It does not persist task text, model output, tool arguments, tokens, or credentials. Requests use the publishable key in `apikey` and the user's access token in `Authorization`; RLS remains the authorization boundary. The client rejects administrative-role JWTs and does not accept an administrative key.

1. Review `supabase/migrations/20261031000000_agent_audit_events.sql` (also mirrored at `supabase/schema/agent_audit_events.sql`) and apply it only to a development/test Supabase project.
2. Expose `agent_audit_events` in the project's Data API settings. New public tables are not automatically exposed by default on current Supabase projects.
3. The table grants authenticated users INSERT only. RLS sets ownership to `auth.uid()` and rejects inserts for another user. No SELECT, UPDATE, or DELETE grant is provided to client roles.
4. Run the pgTAP policy test in `supabase/tests/agent_audit_events_rls_test.sql` against a disposable local Supabase database.

This repository change does not connect to, migrate, or modify any hosted Supabase project. The connected project was inactive during preparation.

## Tests

The Python tests use mocked HTTP transport and a mocked OpenAI client; they do not call OpenAI, the MCP server, or Supabase:

```sh
python -m unittest discover -s examples/reviewed_skill_agent -p 'test_*.py'
```

The SQL pgTAP test runs against the isolated local Supabase stack configured in `supabase/config.toml`. CI applies the migration and runs the RLS test; it does not require hosted credentials or modify the connected project.

## Operational limitations

This is a reference implementation, not a hosted MCP server. Configure a trusted MCP endpoint that implements the named tools and enforces the same policies server-side. The example does not execute local shell commands or modify repositories itself. The named MCP tools are supplied by the separately operated MCP server; this repository does not implement that server. OpenAI model/API availability and account permissions are determined by the configured API account. The CI workflow validates the Python example and local database policies, not connectivity to a live OpenAI or MCP endpoint.
