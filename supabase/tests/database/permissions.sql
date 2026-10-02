-- Run as postgres on a disposable database with all migrations applied:
-- psql "$TEST_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f supabase/tests/database/permissions.sql
BEGIN;

DO $checks$
DECLARE
    client_org UUID := gen_random_uuid();
    agency_org UUID := gen_random_uuid();
    riv3r_org UUID := gen_random_uuid();
    resource_user UUID := gen_random_uuid();
    client_user UUID := gen_random_uuid();
    agency_user UUID := gen_random_uuid();
    riv3r_user UUID := gen_random_uuid();
    extra_permission UUID;
BEGIN
    IF (SELECT count(*) FROM public.permissions) <> 4 THEN
        RAISE EXCEPTION 'expected four seeded permissions';
    END IF;

    INSERT INTO public.organizations (id, company_email, registered_name, industry, org_type)
    VALUES
        (client_org, 'permission-client@example.invalid', 'Client', 'Testing', 'client'),
        (agency_org, 'permission-agency@example.invalid', 'Agency', 'Testing', 'agency'),
        (riv3r_org, 'permission-riv3r@example.invalid', 'RIV3R', 'Testing', 'riv3r');

    INSERT INTO public.users (id, email, password, name, is_resource, org_id)
    VALUES
        (client_user, 'permission-client-user@example.invalid', 'hash', 'Client', false, client_org),
        (agency_user, 'permission-agency-user@example.invalid', 'hash', 'Agency', false, agency_org),
        (riv3r_user, 'permission-riv3r-user@example.invalid', 'hash', 'RIV3R', false, riv3r_org);
    INSERT INTO public.users (id, email, password, name, is_resource)
    VALUES (resource_user, 'permission-resource@example.invalid', 'hash', 'Resource', true);

    INSERT INTO public.organization_members (organization_id, user_id, is_owner)
    VALUES
        (client_org, client_user, true),
        (agency_org, agency_user, true),
        (riv3r_org, riv3r_user, true);

    IF NOT public.user_has_permission(client_user, 'projects.create')
       OR NOT public.user_has_permission(client_user, 'projects.view')
       OR NOT public.user_has_permission(client_user, 'users.view')
       OR NOT public.user_has_permission(client_user, 'projects.publish') THEN
        RAISE EXCEPTION 'client owner grants or dependencies are incomplete';
    END IF;
    IF ARRAY(
        SELECT permission_key FROM public.list_user_permissions(client_user)
    ) <> ARRAY['projects.create', 'projects.publish', 'projects.view', 'users.view'] THEN
        RAISE EXCEPTION 'client effective permission list is incorrect';
    END IF;
    IF NOT public.user_has_permission(agency_user, 'projects.view')
       OR public.user_has_permission(agency_user, 'users.view') THEN
        RAISE EXCEPTION 'agency owner grants are incorrect';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.permissions
        WHERE NOT public.user_has_permission(riv3r_user, permission_key)
    ) THEN
        RAISE EXCEPTION 'RIV3R owner does not have every permission';
    END IF;

    BEGIN
        INSERT INTO public.user_permissions (user_id, permission_id)
        SELECT resource_user, id FROM public.permissions WHERE permission_key = 'projects.view';
        RAISE EXCEPTION 'resource permission was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;

    INSERT INTO public.permissions (permission_key, description)
    VALUES ('tests.extra', 'Test-only permission')
    RETURNING id INTO extra_permission;
    BEGIN
        INSERT INTO public.permission_dependencies (permission_id, depends_on_permission_id)
        SELECT extra_permission, id FROM public.permissions WHERE permission_key = 'projects.create';
        INSERT INTO public.permission_dependencies (permission_id, depends_on_permission_id)
        SELECT id, extra_permission FROM public.permissions WHERE permission_key = 'projects.view';
        RAISE EXCEPTION 'dependency cycle was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;

    IF NOT (SELECT relrowsecurity FROM pg_class WHERE oid = 'public.permissions'::regclass)
       OR NOT (SELECT relrowsecurity FROM pg_class WHERE oid = 'public.user_permissions'::regclass)
       OR NOT (SELECT relrowsecurity FROM pg_class WHERE oid = 'public.permission_dependencies'::regclass) THEN
        RAISE EXCEPTION 'permission table RLS is disabled';
    END IF;
    IF has_table_privilege('anon', 'public.permissions', 'SELECT')
       OR has_table_privilege('authenticated', 'public.user_permissions', 'SELECT') THEN
        RAISE EXCEPTION 'browser roles can access permission tables';
    END IF;
END
$checks$;

ROLLBACK;
