BEGIN;

ALTER TABLE public.projects
    ALTER COLUMN project_embeddings TYPE extensions.vector(1024)
        USING project_embeddings::extensions.vector(1024),
    ADD COLUMN embedding_model TEXT,
    ADD COLUMN embedded_at TIMESTAMPTZ,
    ADD CONSTRAINT projects_drafts_have_no_embeddings CHECK (
        status <> 'draft' OR project_embeddings IS NULL
    ),
    ADD CONSTRAINT projects_embedding_metadata_consistent CHECK (
        (
            project_embeddings IS NULL
            AND embedding_model IS NULL
            AND embedded_at IS NULL
        )
        OR
        (
            project_embeddings IS NOT NULL
            AND embedding_model IS NOT NULL
            AND embedded_at IS NOT NULL
        )
    );

COMMIT;
