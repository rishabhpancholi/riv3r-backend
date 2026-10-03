BEGIN;

DROP TRIGGER IF EXISTS organization_members_grant_owner_permissions
ON public.organization_members;
DROP FUNCTION IF EXISTS public.grant_owner_permissions();

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

    INSERT INTO user_permissions (user_id, permission_id)
    SELECT p_owner_id, permission.id
    FROM permissions AS permission
    WHERE p_org_type = 'riv3r'
       OR (p_org_type = 'client' AND permission.permission_key IN (
            'projects.view', 'projects.create', 'projects.publish', 'users.view'
       ))
       OR (p_org_type = 'agency' AND permission.permission_key IN (
            'projects.view', 'users.view'
       ))
    ON CONFLICT DO NOTHING;

    INSERT INTO refresh_tokens (user_id, refresh_token, expires_at)
    VALUES (p_owner_id, p_refresh_token, p_refresh_expires_at);

    RETURN to_jsonb(created_organization)
        || jsonb_build_object('owner', to_jsonb(created_owner) - 'password');
END;
$$;

-- Align existing owners with the same explicit defaults used by onboarding.
INSERT INTO public.user_permissions (user_id, permission_id)
SELECT member.user_id, permission.id
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
ON CONFLICT DO NOTHING;

REVOKE ALL ON FUNCTION public.onboard_organization_atomic(
    UUID, TEXT, TEXT, TEXT, TEXT, org_type, UUID, TEXT, TEXT, TEXT,
    VARCHAR, TEXT, TIMESTAMPTZ
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.onboard_organization_atomic(
    UUID, TEXT, TEXT, TEXT, TEXT, org_type, UUID, TEXT, TEXT, TEXT,
    VARCHAR, TEXT, TIMESTAMPTZ
) TO service_role;

COMMIT;
