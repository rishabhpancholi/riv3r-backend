-- Run as postgres on a disposable database with all migrations applied:
-- psql "$TEST_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f supabase/tests/database/project_read_support.sql
BEGIN;

DO $test$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'
    ) THEN
        RAISE EXCEPTION 'pg_trgm extension is missing';
    END IF;

    IF to_regclass('public.projects_active_title_trgm_idx') IS NULL
       OR to_regclass('public.projects_active_description_trgm_idx') IS NULL
       OR to_regclass('public.projects_active_domain_trgm_idx') IS NULL THEN
        RAISE EXCEPTION 'one or more project text-search indexes are missing';
    END IF;

    IF to_regclass('public.projects_active_org_created_idx') IS NULL
       OR to_regclass('public.projects_active_created_idx') IS NULL THEN
        RAISE EXCEPTION 'one or more project list-order indexes are missing';
    END IF;
END
$test$;

ROLLBACK;
