CREATE TABLE image_vectors (
    image_id    INT PRIMARY KEY REFERENCES images (id) ON DELETE CASCADE,
    model       TEXT NOT NULL,
    source_text TEXT NOT NULL,
    vector      REAL[] NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE posts (
    id         SERIAL PRIMARY KEY,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE post_vectors (
    post_id    INT PRIMARY KEY REFERENCES posts (id) ON DELETE CASCADE,
    model      TEXT NOT NULL,
    vector     REAL[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
