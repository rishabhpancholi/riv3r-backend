CREATE TYPE actor_type AS ENUM ('user', 'admin');

CREATE TABLE IF NOT EXISTS audit_logs(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    actor actor_type NOT NULL,
    entity_type TEXT NOT NULL,
    task_type TEXT NOT NULL,
    ip_address INET,
    user_agent TEXT,
    request_id UUID,
    time_taken_ms FLOAT
);