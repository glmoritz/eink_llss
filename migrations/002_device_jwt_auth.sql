-- Migration: Device JWT Authentication
-- 
-- This migration adds JWT-based authentication support for devices:
-- - Removes access_token column (replaced by JWT)
-- - Adds auth_status for device authorization workflow
-- - Adds authorized_at and authorized_by for audit
-- - Adds current_refresh_jti for token revocation

-- Add new columns for JWT auth
ALTER TABLE eink.devices
    ADD COLUMN IF NOT EXISTS auth_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS authorized_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS authorized_by VARCHAR(100),
    ADD COLUMN IF NOT EXISTS current_refresh_jti VARCHAR(64);

-- Create index on auth_status for filtering pending devices
CREATE INDEX IF NOT EXISTS ix_devices_auth_status ON eink.devices(auth_status);

-- Migrate existing devices to authorized status
-- (they have access_tokens so they were previously working)
UPDATE eink.devices 
SET auth_status = 'authorized', 
    authorized_at = created_at
WHERE access_token IS NOT NULL AND access_token != '';

-- Drop the access_token column and its index
DROP INDEX IF EXISTS eink.ix_devices_access_token;
ALTER TABLE eink.devices DROP COLUMN IF EXISTS access_token;

-- Verify the changes
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_schema = 'eink' 
  AND table_name = 'devices'
ORDER BY ordinal_position;
