BEGIN;

CREATE TABLE public.permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    permission_key TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT permissions_key_format_check CHECK (
        permission_key ~ '^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$'
    )
);

CREATE TABLE public.user_permissions (
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES public.permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, permission_id)
);

CREATE TABLE public.permission_dependencies (
    permission_id UUID NOT NULL REFERENCES public.permissions(id) ON DELETE CASCADE,
    depends_on_permission_id UUID NOT NULL REFERENCES public.permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (permission_id, depends_on_permission_id),
    CONSTRAINT permission_dependencies_not_self CHECK (
        permission_id <> depends_on_permission_id
    )
);

CREATE INDEX user_permissions_permission_id_idx
    ON public.user_permissions(permission_id);
CREATE INDEX permission_dependencies_depends_on_idx
    ON public.permission_dependencies(depends_on_permission_id);

CREATE FUNCTION public.reject_resource_user_permission()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.users
        WHERE id = NEW.user_id AND is_resource
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'resource users cannot receive permissions';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER user_permissions_reject_resource_user
BEFORE INSERT OR UPDATE ON public.user_permissions
FOR EACH ROW EXECUTE FUNCTION public.reject_resource_user_permission();

CREATE FUNCTION public.reject_permissioned_user_becoming_resource()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
BEGIN
    IF NEW.is_resource AND EXISTS (
        SELECT 1 FROM public.user_permissions WHERE user_id = NEW.id
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'users with permissions cannot become resources';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER users_reject_permissioned_resource_transition
BEFORE UPDATE OF is_resource ON public.users
FOR EACH ROW
WHEN (NEW.is_resource)
EXECUTE FUNCTION public.reject_permissioned_user_becoming_resource();

CREATE FUNCTION public.reject_permission_dependency_cycle()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
BEGIN
    IF NEW.permission_id = NEW.depends_on_permission_id THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'permission cannot depend on itself';
    END IF;

    IF EXISTS (
        WITH RECURSIVE descendants(permission_id) AS (
            SELECT NEW.depends_on_permission_id
            UNION
            SELECT dependency.depends_on_permission_id
            FROM public.permission_dependencies AS dependency
            JOIN descendants
              ON dependency.permission_id = descendants.permission_id
        )
        SELECT 1 FROM descendants WHERE permission_id = NEW.permission_id
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'permission dependency cycle is not allowed';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER permission_dependencies_reject_cycle
BEFORE INSERT OR UPDATE ON public.permission_dependencies
FOR EACH ROW EXECUTE FUNCTION public.reject_permission_dependency_cycle();

INSERT INTO public.permissions (permission_key, description) VALUES
    ('projects.view', 'View projects'),
    ('projects.create', 'Create projects'),
    ('projects.publish', 'Publish draft projects'),
    ('users.view', 'View organization users');

INSERT INTO public.permission_dependencies (
    permission_id, depends_on_permission_id
)
SELECT permission.id, dependency.id
FROM (VALUES
    ('projects.create', 'projects.view'),
    ('projects.create', 'users.view'),
    ('projects.publish', 'projects.view')
) AS required(permission_key, dependency_key)
JOIN public.permissions AS permission
  ON permission.permission_key = required.permission_key
JOIN public.permissions AS dependency
  ON dependency.permission_key = required.dependency_key;

CREATE FUNCTION public.user_has_permission(
    p_user_id UUID,
    p_permission_key TEXT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
    WITH RECURSIVE effective_permissions(permission_id) AS (
        SELECT user_permission.permission_id
        FROM public.user_permissions AS user_permission
        WHERE user_permission.user_id = p_user_id
        UNION
        SELECT dependency.depends_on_permission_id
        FROM public.permission_dependencies AS dependency
        JOIN effective_permissions
          ON effective_permissions.permission_id = dependency.permission_id
    )
    SELECT EXISTS (
        SELECT 1
        FROM effective_permissions
        JOIN public.permissions
          ON permissions.id = effective_permissions.permission_id
        WHERE permissions.permission_key = p_permission_key
    );
$$;

-- Preserve existing capabilities while introducing explicit grants.
INSERT INTO public.user_permissions (user_id, permission_id)
SELECT users.id, permissions.id
FROM public.users
JOIN public.organizations ON organizations.id = users.org_id
JOIN public.permissions ON (
    organizations.org_type = 'riv3r'
    OR (organizations.org_type = 'client'
        AND permissions.permission_key IN ('projects.create', 'projects.publish'))
    OR (organizations.org_type = 'agency'
        AND permissions.permission_key = 'projects.view')
)
WHERE NOT users.is_resource
ON CONFLICT DO NOTHING;

CREATE FUNCTION public.grant_owner_permissions()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    owner_org_type public.org_type;
BEGIN
    IF NOT NEW.is_owner THEN
        RETURN NEW;
    END IF;

    SELECT org_type INTO owner_org_type
    FROM public.organizations
    WHERE id = NEW.organization_id;

    INSERT INTO public.user_permissions (user_id, permission_id)
    SELECT NEW.user_id, permissions.id
    FROM public.permissions
    WHERE owner_org_type = 'riv3r'
       OR (owner_org_type = 'client'
           AND permissions.permission_key IN ('projects.create', 'projects.publish'))
       OR (owner_org_type = 'agency'
           AND permissions.permission_key = 'projects.view')
    ON CONFLICT DO NOTHING;

    RETURN NEW;
END;
$$;

CREATE TRIGGER organization_members_grant_owner_permissions
AFTER INSERT OR UPDATE OF is_owner ON public.organization_members
FOR EACH ROW
WHEN (NEW.is_owner)
EXECUTE FUNCTION public.grant_owner_permissions();

ALTER TABLE public.permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.permission_dependencies ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE public.permissions,
    public.user_permissions,
    public.permission_dependencies
FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.permissions,
    public.user_permissions,
    public.permission_dependencies
TO service_role;

REVOKE ALL ON FUNCTION public.user_has_permission(UUID, TEXT)
FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.user_has_permission(UUID, TEXT)
TO service_role;

REVOKE ALL ON FUNCTION public.reject_resource_user_permission()
FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.reject_permissioned_user_becoming_resource()
FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.reject_permission_dependency_cycle()
FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.grant_owner_permissions()
FROM PUBLIC, anon, authenticated;

COMMIT;
