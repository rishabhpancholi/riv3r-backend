BEGIN;

CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

CREATE TYPE project_status AS ENUM (
    'draft',
    'published',
    'closed',
    'cancelled'
);

CREATE TABLE IF NOT EXISTS public.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    created_by_user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    spoc_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status project_status NOT NULL DEFAULT 'draft',
    deadline_date DATE,
    budget NUMERIC(15, 2),
    currency CHAR(3),
    published_at TIMESTAMPTZ,
    domain TEXT,
    skill_tags TEXT[] NOT NULL DEFAULT '{}',
    project_embeddings extensions.vector,

    CONSTRAINT projects_budget_non_negative CHECK (budget IS NULL OR budget >= 0),
    CONSTRAINT projects_currency_format CHECK (
        currency IS NULL OR currency ~ '^[A-Z]{3}$'
    ),
    CONSTRAINT projects_budget_currency_pair CHECK (
        (budget IS NULL AND currency IS NULL)
        OR (budget IS NOT NULL AND currency IS NOT NULL)
    )
);

CREATE INDEX projects_org_id_idx ON public.projects (org_id);
CREATE INDEX projects_created_by_user_id_idx
    ON public.projects (created_by_user_id);
CREATE INDEX projects_spoc_user_id_idx ON public.projects (spoc_user_id);
CREATE INDEX projects_status_idx ON public.projects (status);
CREATE INDEX projects_deadline_date_idx ON public.projects (deadline_date);
CREATE INDEX projects_skill_tags_idx
    ON public.projects USING GIN (skill_tags);

CREATE TRIGGER projects_updated_at_trigger
BEFORE UPDATE ON public.projects
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE public.projects
FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.projects TO service_role;

COMMIT;
