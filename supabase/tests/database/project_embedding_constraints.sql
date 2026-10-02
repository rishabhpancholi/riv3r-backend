-- Run as postgres on a disposable database with all migrations applied:
-- psql "$TEST_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f supabase/tests/database/project_embedding_constraints.sql
BEGIN;

DO $test$
DECLARE
    organization_id uuid;
    user_id uuid;
    project_id uuid;
    suffix text := gen_random_uuid()::text;
    rejected boolean;
BEGIN
    INSERT INTO public.organizations (company_email, registered_name, industry)
    VALUES ('embedding-org-' || suffix || '@example.invalid', 'Embedding test', 'Testing')
    RETURNING id INTO organization_id;

    INSERT INTO public.users (email, password, name, is_resource, org_id)
    VALUES (
        'embedding-user-' || suffix || '@example.invalid',
        'test-only-hash',
        'Embedding user',
        false,
        organization_id
    )
    RETURNING id INTO user_id;

    INSERT INTO public.projects (
        org_id,
        created_by_user_id,
        spoc_user_id,
        title,
        description,
        deadline_date,
        budget,
        currency,
        domain,
        skill_tags
    )
    VALUES (
        organization_id,
        user_id,
        user_id,
        'Embedding test',
        'Validate embedding constraints',
        CURRENT_DATE + 30,
        100,
        'INR',
        'Testing',
        ARRAY['postgres']
    )
    RETURNING id INTO project_id;

    UPDATE public.projects
    SET status = 'published', published_at = now()
    WHERE id = project_id;

    rejected := false;
    BEGIN
        UPDATE public.projects
        SET project_embeddings = array_fill(0.0, ARRAY[1024])::extensions.vector;
    EXCEPTION WHEN check_violation THEN
        rejected := true;
    END;
    IF NOT rejected THEN
        RAISE EXCEPTION 'Embedding without provenance was accepted';
    END IF;

    UPDATE public.projects
    SET project_embeddings = array_fill(0.0, ARRAY[1024])::extensions.vector,
        embedding_model = 'voyage-4-lite',
        embedded_at = now()
    WHERE id = project_id;

    rejected := false;
    BEGIN
        UPDATE public.projects
        SET project_embeddings = array_fill(0.0, ARRAY[1023])::extensions.vector
        WHERE id = project_id;
    EXCEPTION WHEN data_exception THEN
        rejected := true;
    END;
    IF NOT rejected THEN
        RAISE EXCEPTION 'Wrong embedding dimension was accepted';
    END IF;
END
$test$;

ROLLBACK;
