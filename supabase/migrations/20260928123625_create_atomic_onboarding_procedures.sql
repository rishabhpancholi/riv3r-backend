BEGIN;

ALTER TABLE resources
ADD CONSTRAINT resources_user_id_key UNIQUE (user_id);

CREATE OR REPLACE FUNCTION public.onboard_organization_atomic(
    p_organization_id UUID,
    p_company_email TEXT,
    p_registered_name TEXT,
    p_website_url TEXT,
    p_industry TEXT,
    p_org_type org_type,
    p_owner_id UUID,
    p_owner_email TEXT,
    p_owner_password TEXT,
    p_owner_name TEXT,
    p_owner_phone_number VARCHAR(16),
    p_refresh_token TEXT,
    p_refresh_expires_at TIMESTAMPTZ
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    created_organization organizations%ROWTYPE;
    created_owner users%ROWTYPE;
BEGIN
    -- All onboarding entry points take the same value-scoped locks, preventing
    -- concurrent registrations from passing cross-table duplicate checks.
    PERFORM pg_advisory_xact_lock(hashtextextended('email:' || lower(p_company_email), 0));
    PERFORM pg_advisory_xact_lock(hashtextextended('email:' || lower(p_owner_email), 0));
    IF p_owner_phone_number IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(hashtextextended('phone:' || p_owner_phone_number, 0));
    END IF;
    IF p_website_url IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(hashtextextended('url:' || p_website_url, 0));
    END IF;

    IF EXISTS (SELECT 1 FROM organizations WHERE lower(company_email) = lower(p_company_email))
       OR EXISTS (SELECT 1 FROM users WHERE lower(email) = lower(p_company_email)) THEN
        RAISE EXCEPTION USING ERRCODE = '23505', MESSAGE = 'duplicate onboarding value', DETAIL = 'company_email';
    END IF;
    IF EXISTS (SELECT 1 FROM users WHERE lower(email) = lower(p_owner_email))
       OR EXISTS (SELECT 1 FROM organizations WHERE lower(company_email) = lower(p_owner_email)) THEN
        RAISE EXCEPTION USING ERRCODE = '23505', MESSAGE = 'duplicate onboarding value', DETAIL = 'owner_email';
    END IF;
    IF p_owner_phone_number IS NOT NULL
       AND EXISTS (SELECT 1 FROM users WHERE phone_number = p_owner_phone_number) THEN
        RAISE EXCEPTION USING ERRCODE = '23505', MESSAGE = 'duplicate onboarding value', DETAIL = 'phone_number';
    END IF;
    IF p_website_url IS NOT NULL AND (
        EXISTS (SELECT 1 FROM organizations WHERE website_url = p_website_url)
        OR EXISTS (SELECT 1 FROM resources WHERE portfolio_url = p_website_url OR linked_in_url = p_website_url)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23505', MESSAGE = 'duplicate onboarding value', DETAIL = 'website_url';
    END IF;

    INSERT INTO organizations (
        id, company_email, registered_name, website_url, industry,
        verification_status, org_type
    ) VALUES (
        p_organization_id, p_company_email, p_registered_name, p_website_url,
        p_industry, 'in_progress', p_org_type
    ) RETURNING * INTO created_organization;

    INSERT INTO users (
        id, email, password, name, phone_number, is_resource,
        verification_status, org_id
    ) VALUES (
        p_owner_id, p_owner_email, p_owner_password, p_owner_name,
        p_owner_phone_number, FALSE, 'in_progress', p_organization_id
    ) RETURNING * INTO created_owner;

    INSERT INTO organization_members (organization_id, user_id, is_owner)
    VALUES (p_organization_id, p_owner_id, TRUE);

    INSERT INTO refresh_tokens (user_id, refresh_token, expires_at)
    VALUES (p_owner_id, p_refresh_token, p_refresh_expires_at);

    RETURN to_jsonb(created_organization)
        || jsonb_build_object('owner', to_jsonb(created_owner) - 'password');
END;
$$;

CREATE OR REPLACE FUNCTION public.onboard_resource_atomic(
    p_user_id UUID,
    p_email TEXT,
    p_password TEXT,
    p_name TEXT,
    p_phone_number VARCHAR(16),
    p_title TEXT,
    p_bio TEXT,
    p_location TEXT,
    p_skills JSONB,
    p_experience_years INTEGER,
    p_portfolio_url TEXT,
    p_linked_in_url TEXT,
    p_refresh_token TEXT,
    p_refresh_expires_at TIMESTAMPTZ
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    created_user users%ROWTYPE;
    created_resource resources%ROWTYPE;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('email:' || lower(p_email), 0));
    IF p_phone_number IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(hashtextextended('phone:' || p_phone_number, 0));
    END IF;
    IF p_portfolio_url IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(hashtextextended('url:' || p_portfolio_url, 0));
    END IF;
    IF p_linked_in_url IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock(hashtextextended('url:' || p_linked_in_url, 0));
    END IF;

    IF EXISTS (SELECT 1 FROM users WHERE lower(email) = lower(p_email))
       OR EXISTS (SELECT 1 FROM organizations WHERE lower(company_email) = lower(p_email)) THEN
        RAISE EXCEPTION USING ERRCODE = '23505', MESSAGE = 'duplicate onboarding value', DETAIL = 'email';
    END IF;
    IF p_phone_number IS NOT NULL
       AND EXISTS (SELECT 1 FROM users WHERE phone_number = p_phone_number) THEN
        RAISE EXCEPTION USING ERRCODE = '23505', MESSAGE = 'duplicate onboarding value', DETAIL = 'phone_number';
    END IF;
    IF p_portfolio_url IS NOT NULL AND (
        EXISTS (SELECT 1 FROM organizations WHERE website_url = p_portfolio_url)
        OR EXISTS (SELECT 1 FROM resources WHERE portfolio_url = p_portfolio_url OR linked_in_url = p_portfolio_url)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23505', MESSAGE = 'duplicate onboarding value', DETAIL = 'portfolio_url';
    END IF;
    IF p_linked_in_url IS NOT NULL AND (
        EXISTS (SELECT 1 FROM organizations WHERE website_url = p_linked_in_url)
        OR EXISTS (SELECT 1 FROM resources WHERE portfolio_url = p_linked_in_url OR linked_in_url = p_linked_in_url)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23505', MESSAGE = 'duplicate onboarding value', DETAIL = 'linked_in_url';
    END IF;

    INSERT INTO users (
        id, email, password, name, phone_number, is_resource, verification_status
    ) VALUES (
        p_user_id, p_email, p_password, p_name, p_phone_number, TRUE, 'in_progress'
    ) RETURNING * INTO created_user;

    INSERT INTO resources (
        user_id, title, bio, location, skills, experience_years,
        portfolio_url, linked_in_url
    ) VALUES (
        p_user_id, p_title, p_bio, p_location, p_skills, p_experience_years,
        p_portfolio_url, p_linked_in_url
    ) RETURNING * INTO created_resource;

    INSERT INTO refresh_tokens (user_id, refresh_token, expires_at)
    VALUES (p_user_id, p_refresh_token, p_refresh_expires_at);

    RETURN (to_jsonb(created_user) - 'password')
        || (to_jsonb(created_resource) - ARRAY['id', 'created_at', 'updated_at', 'deleted_at', 'user_id']);
END;
$$;

REVOKE ALL ON FUNCTION public.onboard_organization_atomic(
    UUID, TEXT, TEXT, TEXT, TEXT, org_type, UUID, TEXT, TEXT, TEXT,
    VARCHAR, TEXT, TIMESTAMPTZ
) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.onboard_resource_atomic(
    UUID, TEXT, TEXT, TEXT, VARCHAR, TEXT, TEXT, TEXT, JSONB, INTEGER,
    TEXT, TEXT, TEXT, TIMESTAMPTZ
) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.onboard_organization_atomic(
    UUID, TEXT, TEXT, TEXT, TEXT, org_type, UUID, TEXT, TEXT, TEXT,
    VARCHAR, TEXT, TIMESTAMPTZ
) TO service_role;
GRANT EXECUTE ON FUNCTION public.onboard_resource_atomic(
    UUID, TEXT, TEXT, TEXT, VARCHAR, TEXT, TEXT, TEXT, JSONB, INTEGER,
    TEXT, TEXT, TEXT, TIMESTAMPTZ
) TO service_role;

COMMIT;
