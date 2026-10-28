CREATE TABLE images (
    id          SERIAL PRIMARY KEY,
    filename    TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'processing', 'done', 'flagged', 'failed')),
    attempts    INT NOT NULL DEFAULT 0,
    last_error  TEXT,
    next_try_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    subject     TEXT,
    category    TEXT,
    caption     TEXT,
    confidence  REAL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_images_queue ON images (status, next_try_at);
CREATE INDEX idx_images_category ON images (category);

CREATE TABLE tags (
    id       SERIAL PRIMARY KEY,
    image_id INT NOT NULL REFERENCES images (id) ON DELETE CASCADE,
    tag      TEXT NOT NULL,
    UNIQUE (image_id, tag)
);

CREATE INDEX idx_tags_tag ON tags (tag);
