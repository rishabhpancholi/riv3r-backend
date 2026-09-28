BEGIN;

UPDATE public.projects
SET domain = 'Not Specified'
WHERE domain IS NULL;

ALTER TABLE public.projects
    ALTER COLUMN spoc_user_id SET NOT NULL,
    ALTER COLUMN deadline_date SET NOT NULL,
    ALTER COLUMN budget SET NOT NULL,
    ALTER COLUMN currency SET NOT NULL,
    ALTER COLUMN domain SET DEFAULT 'Not Specified',
    ALTER COLUMN domain SET NOT NULL,
    ADD CONSTRAINT projects_published_status_consistency CHECK (
        (
            published_at IS NULL
            AND status NOT IN ('published', 'closed')
        )
        OR
        (
            published_at IS NOT NULL
            AND status NOT IN ('draft', 'cancelled')
        )
    );

COMMIT;
