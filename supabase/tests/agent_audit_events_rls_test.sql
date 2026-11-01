begin;

select plan(7);

select has_table('public', 'agent_audit_events', 'audit table exists');
select ok(
    (select relrowsecurity from pg_class where oid = 'public.agent_audit_events'::regclass),
    'row level security is enabled'
);
select ok(
    not has_table_privilege('anon', 'public.agent_audit_events', 'INSERT'),
    'anonymous users cannot insert audit events'
);
select ok(
    not has_table_privilege('authenticated', 'public.agent_audit_events', 'SELECT'),
    'authenticated users cannot read audit events through the Data API'
);

set local role authenticated;
select set_config('request.jwt.claim.sub', '11111111-1111-4111-8111-111111111111', true);

select lives_ok(
    $$ insert into public.agent_audit_events (skill_name, event_type, status)
       values ('dependency_audit', 'task_started', 'started') $$,
    'authenticated user can insert an event owned by auth.uid()'
);

select throws_ok(
    $$ insert into public.agent_audit_events (user_id, skill_name, event_type, status)
       values ('22222222-2222-4222-8222-222222222222', 'dependency_audit', 'task_started', 'started') $$,
    '42501',
    null,
    'authenticated user cannot insert an event for another user'
);

reset role;
select is(
    (select count(*)::integer from public.agent_audit_events where user_id = '11111111-1111-4111-8111-111111111111'),
    1,
    'only the authenticated user-owned insert exists'
);

select * from finish();
rollback;
