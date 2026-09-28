BEGIN;

ALTER TABLE public.projects
    ALTER COLUMN currency SET DEFAULT 'INR',
    ADD CONSTRAINT projects_deadline_date_future_check CHECK (
        deadline_date > CURRENT_DATE
    );

COMMIT;
