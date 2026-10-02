BEGIN;

CREATE FUNCTION public.list_user_permissions(p_user_id UUID)
RETURNS TABLE(permission_key TEXT)
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
    SELECT permission.permission_key
    FROM effective_permissions
    JOIN public.permissions AS permission
      ON permission.id = effective_permissions.permission_id
    ORDER BY permission.permission_key;
$$;

REVOKE ALL ON FUNCTION public.list_user_permissions(UUID)
FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.list_user_permissions(UUID)
TO service_role;

COMMIT;
