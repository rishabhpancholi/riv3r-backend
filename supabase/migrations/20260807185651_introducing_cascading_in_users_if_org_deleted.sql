ALTER TABLE users
ADD COLUMN org_id UUID REFERENCES organizations(id) ON DELETE CASCADE;

ALTER TABLE users
ADD CONSTRAINT users_org_id_resource_null_check
CHECK (
    NOT (is_resource = TRUE AND org_id IS NOT NULL)
);
