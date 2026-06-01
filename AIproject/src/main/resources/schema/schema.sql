CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    api_key VARCHAR(255) NOT NULL UNIQUE,
    plan VARCHAR(50) NOT NULL CHECK (plan IN ('FREE', 'PRO')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS research_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    domain VARCHAR(50) NOT NULL CHECK (domain IN ('GENERAL', 'MEDICAL', 'LEGAL', 'TECHNICAL', 'OTHER')),
    depth VARCHAR(20) NOT NULL CHECK (depth IN ('QUICK', 'STANDARD', 'DEEP')),
    fact_check_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    max_sources INTEGER NOT NULL CHECK (max_sources > 0),
    trusted_domains TEXT NOT NULL DEFAULT '[]',
    exclude_domains TEXT NOT NULL DEFAULT '[]',
    status VARCHAR(20) NOT NULL CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    current_stage VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL UNIQUE REFERENCES research_jobs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    key_findings JSONB NOT NULL DEFAULT '[]'::jsonb,
    fact_check_verdict TEXT,
    confidence_score DECIMAL(4,3) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    analyst_insights JSONB,
    output_format VARCHAR(20) NOT NULL CHECK (output_format IN ('JSON', 'MARKDOWN', 'PLAIN')),
    total_sources_found INTEGER NOT NULL DEFAULT 0 CHECK (total_sources_found >= 0),
    total_sources_processed INTEGER NOT NULL DEFAULT 0 CHECK (total_sources_processed >= 0),
    total_time_ms INTEGER NOT NULL DEFAULT 0 CHECK (total_time_ms >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES research_jobs(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title VARCHAR(500),
    domain_name VARCHAR(255),
    scrape_status VARCHAR(20) NOT NULL CHECK (scrape_status IN ('SUCCESS', 'FAILED', 'BLOCKED', 'SKIPPED')),
    content_length INTEGER CHECK (content_length >= 0),
    summary TEXT,
    is_trusted_source BOOLEAN NOT NULL DEFAULT FALSE,
    scraped_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS summary_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url_hash VARCHAR(64) NOT NULL UNIQUE,
    url TEXT NOT NULL,
    domain VARCHAR(50) NOT NULL CHECK (domain IN ('GENERAL', 'MEDICAL', 'LEGAL', 'TECHNICAL', 'OTHER')),
    summary TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0 CHECK (hit_count >= 0)
);

CREATE TABLE IF NOT EXISTS agent_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES research_jobs(id) ON DELETE CASCADE,
    agent_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_ms INTEGER CHECK (duration_ms >= 0),
    llm_calls_made INTEGER NOT NULL DEFAULT 0 CHECK (llm_calls_made >= 0),
    tokens_used INTEGER NOT NULL DEFAULT 0 CHECK (tokens_used >= 0),
    success BOOLEAN NOT NULL,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_research_jobs_user_created
    ON research_jobs (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_research_jobs_status
    ON research_jobs (status);

CREATE INDEX IF NOT EXISTS idx_research_reports_user_created
    ON research_reports (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_sources_job_id
    ON sources (job_id);

CREATE INDEX IF NOT EXISTS idx_sources_scrape_status
    ON sources (scrape_status);

CREATE INDEX IF NOT EXISTS idx_summary_cache_expires_at
    ON summary_cache (expires_at);

CREATE INDEX IF NOT EXISTS idx_agent_metrics_job_agent
    ON agent_metrics (job_id, agent_name);
