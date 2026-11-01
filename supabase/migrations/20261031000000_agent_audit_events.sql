-- User-scoped, append-only audit metadata. Apply only to development/test projects.
create table if not exists public.agent_audit_events (
    event_id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid(),
    skill_name text not null check (skill_name in ('dependency_audit', 'verified_operation')),
    event_type text not null check (event_type in ('task_started', 'approval_requested', 'approval_decision', 'task_completed', 'task_failed')),
    status text not null check (status in ('started', 'pending', 'approved', 'denied', 'completed', 'failed')),
    created_at timestamptz not null default now()
);

alter table public.agent_audit_events enable row level security;

revoke all on table public.agent_audit_events from anon, authenticated;
grant insert on table public.agent_audit_events to authenticated;

create policy "Users may insert their own agent audit events"
    on public.agent_audit_events
    for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

comment on table public.agent_audit_events is
    'Append-only minimal audit metadata. Do not store prompts, tool arguments, model output, or credentials.';
