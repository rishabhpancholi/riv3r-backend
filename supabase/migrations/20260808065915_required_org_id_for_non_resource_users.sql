ALTER TABLE users
ADD CONSTRAINT users_org_id_required_non_resource_check
CHECK (
    NOT (is_resource = FALSE AND org_id IS NULL)
);
