-- LLSS Database Schema
-- PostgreSQL database setup for Low Level Screen Service

-- Create the database (run as superuser)
-- CREATE DATABASE eink_llss;

-- Create the user (run as superuser)
-- CREATE USER eink_root WITH PASSWORD 'eink123';
-- GRANT ALL PRIVILEGES ON DATABASE eink_llss TO eink_root;

-- Connect to the database and run the following:

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create schema
CREATE SCHEMA IF NOT EXISTS eink_llss;

-- Set search path to use eink_llss schema
SET search_path TO eink_llss;

-- Devices table
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) UNIQUE NOT NULL,
    device_secret VARCHAR(64) NOT NULL,
    access_token VARCHAR(64) NOT NULL,
    hardware_id VARCHAR(100) NOT NULL,
    firmware_version VARCHAR(50) NOT NULL,
    
    -- Display capabilities
    display_width INTEGER NOT NULL,
    display_height INTEGER NOT NULL,
    display_bit_depth INTEGER NOT NULL DEFAULT 4,
    display_partial_refresh BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Current state
    current_frame_id VARCHAR(50),
    active_instance_id VARCHAR(50),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    
    -- Indexes
    CONSTRAINT uk_hardware_id UNIQUE (hardware_id)
);

-- Instances table
CREATE TABLE IF NOT EXISTS instances (
    id SERIAL PRIMARY KEY,
    instance_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(100) NOT NULL,
    
    -- Authentication
    access_token VARCHAR(64),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Frames table
CREATE TABLE IF NOT EXISTS frames (
    id SERIAL PRIMARY KEY,
    frame_id VARCHAR(50) UNIQUE NOT NULL,
    instance_id VARCHAR(50),
    
    -- Frame data
    data BYTEA NOT NULL,
    hash VARCHAR(64) NOT NULL,
    
    -- Metadata
    width INTEGER,
    height INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key
    CONSTRAINT fk_instance
        FOREIGN KEY (instance_id)
        REFERENCES instances(instance_id)
        ON DELETE SET NULL
);

-- Device-Instance mapping table
CREATE TABLE IF NOT EXISTS device_instance_map (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    instance_id VARCHAR(50) NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    CONSTRAINT fk_device
        FOREIGN KEY (device_id)
        REFERENCES devices(device_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_instance
        FOREIGN KEY (instance_id)
        REFERENCES instances(instance_id)
        ON DELETE CASCADE,
    
    -- Unique constraint
    CONSTRAINT uk_device_instance UNIQUE (device_id, instance_id)
);

-- Input events table (for logging/debugging)
CREATE TABLE IF NOT EXISTS input_events (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    instance_id VARCHAR(50),
    
    -- Event data
    button VARCHAR(20) NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    event_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key
    CONSTRAINT fk_device
        FOREIGN KEY (device_id)
        REFERENCES devices(device_id)
        ON DELETE CASCADE
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_devices_hardware_id ON devices(hardware_id);
CREATE INDEX IF NOT EXISTS idx_devices_access_token ON devices(access_token);
CREATE INDEX IF NOT EXISTS idx_instances_access_token ON instances(access_token);
CREATE INDEX IF NOT EXISTS idx_frames_instance_id ON frames(instance_id);
CREATE INDEX IF NOT EXISTS idx_frames_created_at ON frames(created_at);
CREATE INDEX IF NOT EXISTS idx_device_instance_map_device ON device_instance_map(device_id);
CREATE INDEX IF NOT EXISTS idx_device_instance_map_instance ON device_instance_map(instance_id);
CREATE INDEX IF NOT EXISTS idx_input_events_device ON input_events(device_id);
CREATE INDEX IF NOT EXISTS idx_input_events_created ON input_events(created_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_devices_updated_at ON devices;
CREATE TRIGGER update_devices_updated_at
    BEFORE UPDATE ON devices
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_instances_updated_at ON instances;
CREATE TRIGGER update_instances_updated_at
    BEFORE UPDATE ON instances
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions to eink_root
GRANT USAGE ON SCHEMA eink_llss TO eink_root;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA eink_llss TO eink_root;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA eink_llss TO eink_root;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA eink_llss TO eink_root;

-- Set default search path for the user
ALTER USER eink_root SET search_path TO eink_llss;
