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

CREATE INDEX IF NOT EXISTS idx_research_jobs_user_created
    ON research_jobs (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_research_jobs_status
    ON research_jobs (status);
