-- Run as postgres on a disposable database with all migrations applied:
-- psql "$TEST_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f supabase/tests/database/permissions.sql
BEGIN;

CREATE FUNCTION pg_temp.reject_forced_refresh_token()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.refresh_token = 'permission-test-forced-failure' THEN
        RAISE EXCEPTION 'forced refresh-token failure';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER permission_test_reject_refresh_token
BEFORE INSERT ON public.refresh_tokens
FOR EACH ROW
EXECUTE FUNCTION pg_temp.reject_forced_refresh_token();

DO $checks$
DECLARE
    client_org UUID := gen_random_uuid();
    agency_org UUID := gen_random_uuid();
    riv3r_org UUID := gen_random_uuid();
    resource_user UUID := gen_random_uuid();
    client_user UUID := gen_random_uuid();
    agency_user UUID := gen_random_uuid();
    riv3r_user UUID := gen_random_uuid();
    failed_org UUID := gen_random_uuid();
    failed_owner UUID := gen_random_uuid();
    extra_permission UUID;
    forced_failure_seen BOOLEAN := FALSE;
BEGIN
    IF (SELECT count(*) FROM public.permissions) <> 4 THEN
        RAISE EXCEPTION 'expected four seeded permissions';
    END IF;

    PERFORM public.onboard_organization_atomic(
        client_org, 'permission-client@example.invalid', 'Client', NULL,
        'Testing', 'client', client_user, 'client-owner@example.invalid',
        'hash', 'Client Owner', NULL, 'client-refresh', now() + interval '1 day'
    );
    PERFORM public.onboard_organization_atomic(
        agency_org, 'permission-agency@example.invalid', 'Agency', NULL,
        'Testing', 'agency', agency_user, 'agency-owner@example.invalid',
        'hash', 'Agency Owner', NULL, 'agency-refresh', now() + interval '1 day'
    );
    PERFORM public.onboard_organization_atomic(
        riv3r_org, 'permission-riv3r@example.invalid', 'RIV3R', NULL,
        'Testing', 'riv3r', riv3r_user, 'riv3r-owner@example.invalid',
        'hash', 'RIV3R Owner', NULL, 'riv3r-refresh', now() + interval '1 day'
    );

    INSERT INTO public.users (id, email, password, name, is_resource)
    VALUES (resource_user, 'permission-resource@example.invalid', 'hash', 'Resource', true);

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
       OR NOT public.user_has_permission(agency_user, 'users.view') THEN
        RAISE EXCEPTION 'agency owner grants are incorrect';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.permissions
        WHERE NOT public.user_has_permission(riv3r_user, permission_key)
    ) THEN
        RAISE EXCEPTION 'RIV3R owner does not have every permission';
    END IF;
    IF (SELECT count(*) FROM public.user_permissions WHERE user_id = client_user) <> 4
       OR (SELECT count(*) FROM public.user_permissions WHERE user_id = agency_user) <> 2
       OR (SELECT count(*) FROM public.user_permissions WHERE user_id = riv3r_user) <> 4 THEN
        RAISE EXCEPTION 'owner permissions were not stored as direct grants';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgrelid = 'public.organization_members'::regclass
          AND tgname = 'organization_members_grant_owner_permissions'
          AND NOT tgisinternal
    ) THEN
        RAISE EXCEPTION 'obsolete owner permission trigger still exists';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM public.organization_members AS member
        JOIN public.users AS owner ON owner.id = member.user_id
        JOIN public.organizations AS organization
          ON organization.id = member.organization_id
        JOIN public.permissions AS permission ON (
            organization.org_type = 'riv3r'
            OR (organization.org_type = 'client' AND permission.permission_key IN (
                'projects.view', 'projects.create', 'projects.publish', 'users.view'
            ))
            OR (organization.org_type = 'agency' AND permission.permission_key IN (
                'projects.view', 'users.view'
            ))
        )
        WHERE member.is_owner
          AND NOT owner.is_resource
          AND NOT EXISTS (
              SELECT 1 FROM public.user_permissions AS user_permission
              WHERE user_permission.user_id = member.user_id
                AND user_permission.permission_id = permission.id
          )
    ) THEN
        RAISE EXCEPTION 'an existing owner is missing a default direct grant';
    END IF;

    BEGIN
        PERFORM public.onboard_organization_atomic(
            failed_org, 'permission-failed@example.invalid', 'Failed', NULL,
            'Testing', 'client', failed_owner, 'failed-owner@example.invalid',
            'hash', 'Failed Owner', NULL, 'permission-test-forced-failure',
            now() + interval '1 day'
        );
    EXCEPTION WHEN raise_exception THEN
        forced_failure_seen := TRUE;
    END;
    IF NOT forced_failure_seen THEN
        RAISE EXCEPTION 'forced onboarding failure did not occur';
    END IF;
    IF EXISTS (SELECT 1 FROM public.organizations WHERE id = failed_org)
       OR EXISTS (SELECT 1 FROM public.users WHERE id = failed_owner)
       OR EXISTS (SELECT 1 FROM public.organization_members WHERE user_id = failed_owner)
       OR EXISTS (SELECT 1 FROM public.user_permissions WHERE user_id = failed_owner) THEN
        RAISE EXCEPTION 'failed onboarding left partial rows';
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
