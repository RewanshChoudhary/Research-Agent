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

CREATE INDEX IF NOT EXISTS idx_agent_metrics_job_agent
    ON agent_metrics (job_id, agent_name);
