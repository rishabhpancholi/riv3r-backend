-- Run as postgres on a disposable database with all migrations applied:
-- psql "$TEST_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f supabase/tests/database/onboarding_duplicates.sql
BEGIN;

CREATE FUNCTION pg_temp.reject_forced_refresh_token()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.refresh_token = 'duplicates-forced-failure' THEN
        RAISE EXCEPTION 'forced refresh-token failure';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER onboarding_duplicates_reject_refresh_token
BEFORE INSERT ON public.refresh_tokens
FOR EACH ROW
EXECUTE FUNCTION pg_temp.reject_forced_refresh_token();

DO $checks$
DECLARE
    base_org UUID := gen_random_uuid();
    base_owner UUID := gen_random_uuid();
    failed_org UUID := gen_random_uuid();
    failed_owner UUID := gen_random_uuid();
    duplicate_org UUID := gen_random_uuid();
    duplicate_owner UUID := gen_random_uuid();
    duplicate_user UUID := gen_random_uuid();
    duplicate_detail TEXT;
    duplicate_message TEXT;
    remaining_organizations BIGINT;
    remaining_users BIGINT;
    remaining_memberships BIGINT;
    remaining_permissions BIGINT;
    remaining_refresh_tokens BIGINT;
    resource_user UUID := gen_random_uuid();
    resource_phone_detail TEXT;
BEGIN
    PERFORM public.onboard_organization_atomic(
        base_org, 'duplicates-base@example.invalid', 'Base', NULL,
        'Testing', 'client', base_owner, 'duplicates-base-owner@example.invalid',
        'hash', 'Base Owner', '+15550000001', 'base-refresh',
        now() + interval '1 day'
    );

    -- Organization onboarding must report duplicate owner phones with the
    -- normalized detail that matches the RPC parameter name.
    BEGIN
        PERFORM public.onboard_organization_atomic(
            duplicate_org, 'duplicates-new@example.invalid', 'Duplicate', NULL,
            'Testing', 'client', duplicate_owner,
            'duplicates-new-owner@example.invalid', 'hash', 'Duplicate Owner',
            '+15550000001', 'duplicate-refresh', now() + interval '1 day'
        );
        RAISE EXCEPTION 'duplicate owner phone was accepted';
    EXCEPTION
        WHEN unique_violation THEN
            GET STACKED DIAGNOSTICS duplicate_detail = PG_EXCEPTION_DETAIL,
                duplicate_message = PG_EXCEPTION_MESSAGE;
    END;
    IF duplicate_detail IS DISTINCT FROM 'owner_phone_number' THEN
        RAISE EXCEPTION 'expected owner_phone_number detail, got %', duplicate_detail;
    END IF;
    IF duplicate_message IS DISTINCT FROM 'duplicate onboarding value' THEN
        RAISE EXCEPTION 'unexpected duplicate message: %', duplicate_message;
    END IF;

    -- A forced refresh-token failure after the duplicate checks must still
    -- leave no partial onboarding rows behind.
    BEGIN
        PERFORM public.onboard_organization_atomic(
            failed_org, 'duplicates-failed@example.invalid', 'Failed', NULL,
            'Testing', 'client', failed_owner,
            'duplicates-failed-owner@example.invalid', 'hash', 'Failed Owner',
            NULL, 'duplicates-forced-failure', now() + interval '1 day'
        );
        RAISE EXCEPTION 'forced onboarding failure did not occur';
    EXCEPTION
        WHEN raise_exception THEN
            NULL;
    END;
    SELECT count(*) INTO remaining_organizations
    FROM public.organizations WHERE id = failed_org;
    SELECT count(*) INTO remaining_users FROM public.users WHERE id = failed_owner;
    SELECT count(*) INTO remaining_memberships
    FROM public.organization_members WHERE user_id = failed_owner;
    SELECT count(*) INTO remaining_permissions
    FROM public.user_permissions WHERE user_id = failed_owner;
    SELECT count(*) INTO remaining_refresh_tokens
    FROM public.refresh_tokens
    WHERE refresh_token = 'duplicates-forced-failure';
    IF remaining_organizations <> 0 OR remaining_users <> 0
       OR remaining_memberships <> 0 OR remaining_permissions <> 0
       OR remaining_refresh_tokens <> 0 THEN
        RAISE EXCEPTION 'failed onboarding left partial rows';
    END IF;

    -- Duplicate company emails keep their own detail spelling.
    BEGIN
        PERFORM public.onboard_organization_atomic(
            duplicate_org, 'duplicates-base@example.invalid', 'Duplicate', NULL,
            'Testing', 'client', duplicate_owner,
            'duplicates-other-owner@example.invalid', 'hash', 'Other Owner',
            NULL, 'other-refresh', now() + interval '1 day'
        );
        RAISE EXCEPTION 'duplicate company email was accepted';
    EXCEPTION
        WHEN unique_violation THEN
            GET STACKED DIAGNOSTICS duplicate_detail = PG_EXCEPTION_DETAIL;
    END;
    IF duplicate_detail IS DISTINCT FROM 'company_email' THEN
        RAISE EXCEPTION 'expected company_email detail, got %', duplicate_detail;
    END IF;

    -- Resource onboarding checks phones against every user, including
    -- organization owners, and keeps the users-table column as its detail.
    INSERT INTO public.users (id, email, password, name, phone_number, is_resource)
    VALUES (
        resource_user, 'duplicates-resource-owner@example.invalid', 'hash',
        'Resource User', '+15550000001', false
    );
    BEGIN
        PERFORM public.onboard_resource_atomic(
            duplicate_user, 'duplicates-resource@example.invalid', 'hash',
            'Resource', '+15550000001', 'Title', NULL, NULL, '["python"]'::jsonb,
            1, NULL, NULL, 'resource-refresh', now() + interval '1 day'
        );
        RAISE EXCEPTION 'resource duplicate phone was accepted';
    EXCEPTION
        WHEN unique_violation THEN
            GET STACKED DIAGNOSTICS resource_phone_detail = PG_EXCEPTION_DETAIL;
    END;
    IF resource_phone_detail IS DISTINCT FROM 'phone_number' THEN
        RAISE EXCEPTION 'expected phone_number detail, got %', resource_phone_detail;
    END IF;
END
$checks$;

ROLLBACK;
