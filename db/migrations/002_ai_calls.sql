CREATE TABLE ai_calls (
    id            SERIAL PRIMARY KEY,
    image_id      INT REFERENCES images (id) ON DELETE SET NULL,
    purpose       TEXT NOT NULL CHECK (purpose IN ('vision', 'embedding')),
    model         TEXT NOT NULL,
    input_tokens  INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    cost_usd      NUMERIC(12, 6) NOT NULL DEFAULT 0,
    latency_ms    INT NOT NULL DEFAULT 0,
    status        TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_calls_image ON ai_calls (image_id);
CREATE INDEX idx_ai_calls_created ON ai_calls (created_at);
