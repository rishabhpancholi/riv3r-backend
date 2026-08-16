-- Create a verification_status enum with the three allowed values
CREATE TYPE verification_status AS ENUM ('in_progress', 'approved', 'rejected');

-- Add the new column to users, backfill from is_verified, then drop is_verified
ALTER TABLE users
    ADD COLUMN verification_status verification_status DEFAULT 'in_progress';

UPDATE users
SET verification_status = CASE
    WHEN is_verified THEN 'approved'::verification_status
    ELSE 'in_progress'::verification_status
END;

ALTER TABLE users
    ALTER COLUMN verification_status SET NOT NULL,
    DROP COLUMN is_verified;

-- Add the new column to organizations, backfill from is_verified, then drop is_verified
ALTER TABLE organizations
    ADD COLUMN verification_status verification_status DEFAULT 'in_progress';

UPDATE organizations
SET verification_status = CASE
    WHEN is_verified THEN 'approved'::verification_status
    ELSE 'in_progress'::verification_status
END;

ALTER TABLE organizations
    ALTER COLUMN verification_status SET NOT NULL,
    DROP COLUMN is_verified;
