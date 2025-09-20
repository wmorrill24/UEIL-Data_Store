-- Database initialization script
-- This creates the necessary tables for the data lake system

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create folders table
CREATE TABLE IF NOT EXISTS public.folders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    key_prefix VARCHAR(500) NOT NULL,
    project VARCHAR(100) NOT NULL,
    author VARCHAR(100) NOT NULL,
    experiment_type VARCHAR(200),
    date_conducted DATE,
    tags JSONB DEFAULT '[]'::jsonb,
    notes TEXT,
    immutable BOOLEAN DEFAULT true,
    file_count INTEGER DEFAULT 0,
    total_size BIGINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create file_index table
CREATE TABLE IF NOT EXISTS public.file_index (
    file_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    folder_id UUID REFERENCES public.folders(id),
    bucket VARCHAR(100) NOT NULL,
    object_name VARCHAR(1000) NOT NULL,
    relative_path VARCHAR(1000),
    original_filename VARCHAR(500) NOT NULL,
    stored_filename VARCHAR(500),
    extension VARCHAR(50),
    content_type VARCHAR(100),
    size_bytes BIGINT,
    checksum_etag VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    project VARCHAR(100),
    author VARCHAR(100),
    experiment_type VARCHAR(200),
    date_conducted DATE,
    tags JSONB DEFAULT '[]'::jsonb
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_file_index_project ON public.file_index(project);
CREATE INDEX IF NOT EXISTS idx_file_index_author ON public.file_index(author);
CREATE INDEX IF NOT EXISTS idx_file_index_created_at ON public.file_index(created_at);
CREATE INDEX IF NOT EXISTS idx_file_index_folder_id ON public.file_index(folder_id);
CREATE INDEX IF NOT EXISTS idx_folders_project ON public.folders(project);
CREATE INDEX IF NOT EXISTS idx_folders_author ON public.folders(author);
