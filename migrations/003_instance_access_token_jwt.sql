-- Migration: Expand instance access_token to support JWT
--
-- This migration updates the instances.access_token column to TEXT
-- so it can store JWTs signed with HLSS_SHARED_KEY.

-- Drop index on access_token (JWTs are long and no longer used for lookup)
DROP INDEX IF EXISTS eink.ix_instances_access_token;

-- Expand column to TEXT
ALTER TABLE eink.instances
    ALTER COLUMN access_token TYPE TEXT;

-- Verify the changes
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'eink'
  AND table_name = 'instances'
  AND column_name = 'access_token';
