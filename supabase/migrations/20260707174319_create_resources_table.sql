CREATE TABLE IF NOT EXISTS resources(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    bio TEXT,
    location TEXT,
    skills JSONB,
    experience_years INTEGER NOT NULL DEFAULT 0,
    portfolio_url TEXT,
    linked_in_url TEXT,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP DEFAULT null
);

CREATE TRIGGER resources_updated_at_trigger
BEFORE INSERT ON resources
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();