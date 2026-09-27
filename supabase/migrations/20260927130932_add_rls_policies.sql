BEGIN;

-- Custom application JWTs are verified by FastAPI. Only the backend's
-- service_role may access these tables through the Supabase Data API.
DO $migration$
DECLARE
    target_table text;
    existing_policy record;
    column_names text;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'users', 'organizations', 'organization_members',
        'resources', 'refresh_tokens', 'audit_logs'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', target_table);

        FOR existing_policy IN
            SELECT policyname FROM pg_catalog.pg_policies
            WHERE schemaname = 'public' AND tablename = target_table
        LOOP
            EXECUTE format('DROP POLICY %I ON public.%I', existing_policy.policyname, target_table);
        END LOOP;

        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM PUBLIC, anon, authenticated',
            target_table
        );

        -- Table-level REVOKE does not remove independent column grants.
        SELECT string_agg(quote_ident(attname), ', ' ORDER BY attnum)
        INTO column_names
        FROM pg_catalog.pg_attribute
        WHERE attrelid = format('public.%I', target_table)::regclass
          AND attnum > 0 AND NOT attisdropped;

        EXECUTE format(
            'REVOKE ALL PRIVILEGES (%s) ON TABLE public.%I FROM PUBLIC, anon, authenticated',
            column_names, target_table
        );
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO service_role',
            target_table
        );
    END LOOP;
END
$migration$;

-- No client policies: RLS defaults to deny. service_role bypasses RLS.
COMMIT;
