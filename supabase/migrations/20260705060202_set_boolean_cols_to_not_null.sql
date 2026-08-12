ALTER TABLE users
ALTER COLUMN is_resource SET NOT NULL,
ALTER COLUMN is_verified SET NOT NULL;

ALTER TABLE organizations
ALTER COLUMN is_verified SET NOT NULL;

ALTER TABLE organization_members
ALTER COLUMN is_owner SET NOT NULL;

ALTER TABLE refresh_tokens
ALTER COLUMN is_blacklisted SET NOT NULL;