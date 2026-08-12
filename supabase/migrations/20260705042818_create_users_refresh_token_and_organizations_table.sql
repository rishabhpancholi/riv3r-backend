CREATE TYPE org_type AS ENUM ('client', 'agency', 'riv3r');
CREATE TYPE org_membership_status AS ENUM ('inactive', 'active');

CREATE TABLE IF NOT EXISTS users(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    phone_number VARCHAR(16),
    is_resource BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP DEFAULT null
);

CREATE TABLE IF NOT EXISTS organizations(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_email TEXT UNIQUE NOT NULL,
    registered_name TEXT NOT NULL,
    website_url TEXT,
    industry TEXT NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    org_type org_type NOT NULL DEFAULT 'client',
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP DEFAULT null
);

CREATE TABLE IF NOT EXISTS organization_members(
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT now(),
    status org_membership_status NOT NULL DEFAULT 'active',
    is_owner BOOLEAN DEFAULT FALSE,

    PRIMARY KEY (organization_id, user_id)
);

CREATE TABLE IF NOT EXISTS refresh_tokens(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token TEXT NOT NULL,
    is_blacklisted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION prevent_resource_membership()
RETURNS TRIGGER AS $$
BEGIN
   IF EXISTS (
        SELECT 1
        FROM users
        WHERE id = NEW.user_id
          AND is_resource = TRUE
    ) THEN
        RAISE EXCEPTION 'Resource users cannot be organization members.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prevent_resource_membership_trigger
BEFORE INSERT OR UPDATE
ON organization_members
FOR EACH ROW
EXECUTE FUNCTION prevent_resource_membership();

CREATE TRIGGER organization_members_updated_at_trigger
BEFORE UPDATE ON organization_members
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER users_updated_at_trigger
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER organizations_updated_at_trigger
BEFORE UPDATE ON organizations
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER refresh_tokens_updated_at_trigger
BEFORE UPDATE ON refresh_tokens
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();