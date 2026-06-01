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

CREATE INDEX IF NOT EXISTS idx_sources_job_id
    ON sources (job_id);

CREATE INDEX IF NOT EXISTS idx_sources_scrape_status
    ON sources (scrape_status);
