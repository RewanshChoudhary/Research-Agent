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

CREATE INDEX IF NOT EXISTS idx_research_reports_user_created
    ON research_reports (user_id, created_at DESC);
