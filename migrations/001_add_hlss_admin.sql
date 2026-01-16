-- LLSS Database Migration: Add HLSS Admin Support
-- Run this script to add the new tables and columns for HLSS management

-- Set search path
SET search_path TO eink_llss;

-- ============================================================
-- Create hlss_types table
-- ============================================================
CREATE TABLE IF NOT EXISTS hlss_types (
    id SERIAL PRIMARY KEY,
    type_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    base_url VARCHAR(500) NOT NULL,
    auth_token VARCHAR(255),
    
    -- Display defaults
    default_width INTEGER,
    default_height INTEGER,
    default_bit_depth INTEGER,
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hlss_types_type_id ON hlss_types(type_id);

-- ============================================================
-- Add new columns to instances table
-- ============================================================

-- HLSS type reference
ALTER TABLE instances 
ADD COLUMN IF NOT EXISTS hlss_type_id VARCHAR(50);

-- Add foreign key constraint (only if column was just added)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_instances_hlss_type' 
        AND table_schema = 'eink_llss'
    ) THEN
        ALTER TABLE instances
        ADD CONSTRAINT fk_instances_hlss_type
        FOREIGN KEY (hlss_type_id)
        REFERENCES hlss_types(type_id)
        ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_instances_hlss_type_id ON instances(hlss_type_id);

-- HLSS initialization state
ALTER TABLE instances 
ADD COLUMN IF NOT EXISTS hlss_initialized BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE instances 
ADD COLUMN IF NOT EXISTS hlss_ready BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE instances 
ADD COLUMN IF NOT EXISTS needs_configuration BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE instances 
ADD COLUMN IF NOT EXISTS configuration_url VARCHAR(500);

-- Display configuration
ALTER TABLE instances 
ADD COLUMN IF NOT EXISTS display_width INTEGER;

ALTER TABLE instances 
ADD COLUMN IF NOT EXISTS display_height INTEGER;

ALTER TABLE instances 
ADD COLUMN IF NOT EXISTS display_bit_depth INTEGER;

-- Initialization timestamp
ALTER TABLE instances 
ADD COLUMN IF NOT EXISTS initialized_at TIMESTAMP WITH TIME ZONE;

-- ============================================================
-- Update existing instances to have default values
-- ============================================================
UPDATE instances 
SET hlss_initialized = FALSE, 
    hlss_ready = FALSE, 
    needs_configuration = FALSE
WHERE hlss_initialized IS NULL;

-- ============================================================
-- Verification
-- ============================================================
-- Run this to verify the migration was successful:
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_schema = 'eink_llss' AND table_name = 'instances'
-- ORDER BY ordinal_position;

-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_schema = 'eink_llss' AND table_name = 'hlss_types'
-- ORDER BY ordinal_position;
