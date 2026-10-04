BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;

WITH normalized AS (
    SELECT
        project.id,
        COALESCE((
            SELECT array_agg(tag ORDER BY first_position)
            FROM (
                SELECT
                    lower(btrim(item.value)) AS tag,
                    min(item.position) AS first_position
                FROM unnest(project.skill_tags) WITH ORDINALITY
                    AS item(value, position)
                WHERE btrim(item.value) <> ''
                GROUP BY lower(btrim(item.value))
            ) AS unique_tags
        ), ARRAY[]::TEXT[]) AS tags
    FROM public.projects AS project
)
UPDATE public.projects AS project
SET skill_tags = normalized.tags
FROM normalized
WHERE project.id = normalized.id
  AND project.skill_tags IS DISTINCT FROM normalized.tags;

CREATE INDEX projects_active_title_trgm_idx
    ON public.projects USING GIN (title extensions.gin_trgm_ops)
    WHERE deleted_at IS NULL;
CREATE INDEX projects_active_description_trgm_idx
    ON public.projects USING GIN (description extensions.gin_trgm_ops)
    WHERE deleted_at IS NULL;
CREATE INDEX projects_active_domain_trgm_idx
    ON public.projects USING GIN (domain extensions.gin_trgm_ops)
    WHERE deleted_at IS NULL;
CREATE INDEX projects_active_org_created_idx
    ON public.projects (org_id, created_at DESC, id DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX projects_active_created_idx
    ON public.projects (created_at DESC, id DESC)
    WHERE deleted_at IS NULL;

COMMIT;
