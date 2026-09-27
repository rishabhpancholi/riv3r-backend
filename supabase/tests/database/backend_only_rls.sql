-- Run as postgres on a disposable database with all migrations applied:
-- psql "$TEST_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f supabase/tests/database/backend_only_rls.sql
-- This is a standalone SQL assertion suite; no pgTAP extension is required.
BEGIN;

CREATE TEMP TABLE rls_fixtures (table_name text PRIMARY KEY, row_data jsonb);
GRANT SELECT, INSERT ON rls_fixtures TO service_role;

-- Exercise actual service-role inserts on every protected table.
SET LOCAL ROLE service_role;
DO $fixtures$
DECLARE
    org_id uuid;
    member_id uuid;
    resource_user_id uuid;
    fixture jsonb;
    suffix text := gen_random_uuid()::text;
BEGIN
    INSERT INTO public.organizations (company_email, registered_name, industry)
    VALUES ('rls-org-' || suffix || '@example.invalid', 'RLS test', 'Testing')
    RETURNING id, to_jsonb(organizations.*) INTO org_id, fixture;
    INSERT INTO rls_fixtures VALUES ('organizations', fixture);

    INSERT INTO public.users (email, password, name, is_resource, org_id)
    VALUES ('rls-member-' || suffix || '@example.invalid', 'test-only-hash', 'RLS member', false, org_id)
    RETURNING id INTO member_id;

    INSERT INTO public.users (email, password, name, is_resource)
    VALUES ('rls-resource-' || suffix || '@example.invalid', 'test-only-hash', 'RLS resource', true)
    RETURNING id, to_jsonb(users.*) INTO resource_user_id, fixture;
    INSERT INTO rls_fixtures VALUES ('users', fixture);

    INSERT INTO public.organization_members (organization_id, user_id, is_owner)
    VALUES (org_id, member_id, true)
    RETURNING to_jsonb(organization_members.*) INTO fixture;
    INSERT INTO rls_fixtures VALUES ('organization_members', fixture);

    INSERT INTO public.resources (title, user_id)
    VALUES ('RLS test resource', resource_user_id)
    RETURNING to_jsonb(resources.*) INTO fixture;
    INSERT INTO rls_fixtures VALUES ('resources', fixture);

    INSERT INTO public.refresh_tokens (user_id, refresh_token)
    VALUES (resource_user_id, 'test-only-token-' || suffix)
    RETURNING to_jsonb(refresh_tokens.*) INTO fixture;
    INSERT INTO rls_fixtures VALUES ('refresh_tokens', fixture);

    INSERT INTO public.audit_logs (user_id, actor, entity_type, task_type)
    VALUES (resource_user_id, 'user', 'resource', 'rls_test')
    RETURNING to_jsonb(audit_logs.*) INTO fixture;
    INSERT INTO rls_fixtures VALUES ('audit_logs', fixture);
END
$fixtures$;
RESET ROLE;

DO $checks$
DECLARE
    fixture record;
    client_role text;
    operation text;
    statement text;
    key_column text;
    affected bigint;
    allowed boolean;
BEGIN
    FOR fixture IN SELECT * FROM rls_fixtures LOOP
        IF NOT (SELECT relrowsecurity FROM pg_class
                WHERE oid = format('public.%I', fixture.table_name)::regclass) THEN
            RAISE EXCEPTION 'RLS disabled: %', fixture.table_name;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_policies
                   WHERE schemaname = 'public' AND tablename = fixture.table_name) THEN
            RAISE EXCEPTION 'Unexpected policy: %', fixture.table_name;
        END IF;
        key_column := CASE WHEN fixture.table_name = 'organization_members'
                           THEN 'organization_id' ELSE 'id' END;

        FOREACH client_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
            FOREACH operation IN ARRAY ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'] LOOP
                IF has_table_privilege(client_role, format('public.%I', fixture.table_name), operation) THEN
                    RAISE EXCEPTION 'Unexpected % grant for % on %', operation, client_role, fixture.table_name;
                END IF;
            END LOOP;
            FOREACH operation IN ARRAY ARRAY['SELECT', 'INSERT', 'UPDATE', 'REFERENCES'] LOOP
                IF has_any_column_privilege(client_role, format('public.%I', fixture.table_name), operation) THEN
                    RAISE EXCEPTION 'Unexpected column % grant for % on %', operation, client_role, fixture.table_name;
                END IF;
            END LOOP;

            -- First prove grants reject actual requests, even for empty queries.
            FOREACH statement IN ARRAY ARRAY[
                format('SELECT * FROM public.%I', fixture.table_name),
                format('INSERT INTO public.%I SELECT (jsonb_populate_record(NULL::public.%I, %L::jsonb)).*', fixture.table_name, fixture.table_name, fixture.row_data),
                format('UPDATE public.%I SET %I = %I', fixture.table_name, key_column, key_column),
                format('DELETE FROM public.%I', fixture.table_name)
            ] LOOP
                EXECUTE format('SET LOCAL ROLE %I', client_role);
                allowed := false;
                BEGIN
                    EXECUTE statement;
                    allowed := true;
                EXCEPTION WHEN insufficient_privilege THEN
                    NULL;
                END;
                RESET ROLE;
                IF allowed THEN
                    RAISE EXCEPTION 'Client request unexpectedly allowed: % as %', statement, client_role;
                END IF;
            END LOOP;

            -- Temporarily restore CRUD grants to test RLS independently.
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO %I', fixture.table_name, client_role);
            EXECUTE format('SET LOCAL ROLE %I', client_role);
            EXECUTE format('SELECT count(*) FROM public.%I', fixture.table_name) INTO affected;
            IF affected <> 0 THEN
                RAISE EXCEPTION 'RLS leaked rows: % as %', fixture.table_name, client_role;
            END IF;
            EXECUTE format('UPDATE public.%I SET %I = %I', fixture.table_name, key_column, key_column);
            GET DIAGNOSTICS affected = ROW_COUNT;
            IF affected <> 0 THEN
                RAISE EXCEPTION 'RLS allowed update: %', fixture.table_name;
            END IF;
            EXECUTE format('DELETE FROM public.%I', fixture.table_name);
            GET DIAGNOSTICS affected = ROW_COUNT;
            IF affected <> 0 THEN
                RAISE EXCEPTION 'RLS allowed delete: %', fixture.table_name;
            END IF;
            allowed := false;
            BEGIN
                EXECUTE format(
                    'INSERT INTO public.%I SELECT (jsonb_populate_record(NULL::public.%I, %L::jsonb)).*',
                    fixture.table_name, fixture.table_name, fixture.row_data
                );
                allowed := true;
            EXCEPTION WHEN insufficient_privilege THEN
                NULL;
            END;
            RESET ROLE;
            IF allowed THEN
                RAISE EXCEPTION 'RLS allowed insert: %', fixture.table_name;
            END IF;
            EXECUTE format('REVOKE SELECT, INSERT, UPDATE, DELETE ON public.%I FROM %I', fixture.table_name, client_role);
        END LOOP;

        EXECUTE 'SET LOCAL ROLE service_role';
        EXECUTE format('SELECT count(*) FROM public.%I WHERE %I = %L::uuid',
                       fixture.table_name, key_column, fixture.row_data ->> key_column) INTO affected;
        RESET ROLE;
        IF affected <> 1 THEN
            RAISE EXCEPTION 'Service role cannot read fixture: %', fixture.table_name;
        END IF;
    END LOOP;
END
$checks$;

SET LOCAL ROLE service_role;
DO $service_writes$
DECLARE
    resource_id uuid := (SELECT (row_data ->> 'id')::uuid FROM rls_fixtures WHERE table_name = 'resources');
    affected bigint;
BEGIN
    UPDATE public.resources SET title = 'RLS updated resource' WHERE id = resource_id;
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 1 THEN RAISE EXCEPTION 'Service-role update failed'; END IF;
    DELETE FROM public.resources WHERE id = resource_id;
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 1 THEN RAISE EXCEPTION 'Service-role delete failed'; END IF;
END
$service_writes$;
RESET ROLE;

ROLLBACK;
