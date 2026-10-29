ALTER TABLE posts
    ADD COLUMN subject    TEXT,
    ADD COLUMN category   TEXT,
    ADD COLUMN confidence REAL;

CREATE TABLE suggestions (
    id         SERIAL PRIMARY KEY,
    post_id    INT NOT NULL REFERENCES posts (id) ON DELETE CASCADE,
    image_id   INT NOT NULL REFERENCES images (id) ON DELETE CASCADE,
    rank       INT NOT NULL,
    score      REAL NOT NULL,
    decision   TEXT NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    rule       TEXT,
    reason     TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (post_id, image_id)
);

CREATE INDEX idx_suggestions_post ON suggestions (post_id, rank);

CREATE TABLE reviews (
    id            SERIAL PRIMARY KEY,
    suggestion_id INT NOT NULL REFERENCES suggestions (id) ON DELETE CASCADE,
    verdict       TEXT NOT NULL CHECK (verdict IN ('approved', 'rejected')),
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_reviews_suggestion ON reviews (suggestion_id);

CREATE TABLE jobs (
    id          SERIAL PRIMARY KEY,
    kind        TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('running', 'done', 'failed')),
    total       INT NOT NULL DEFAULT 0,
    done        INT NOT NULL DEFAULT 0,
    failed      INT NOT NULL DEFAULT 0,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);
