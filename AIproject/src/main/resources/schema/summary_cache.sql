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

CREATE INDEX IF NOT EXISTS idx_summary_cache_expires_at
    ON summary_cache (expires_at);
