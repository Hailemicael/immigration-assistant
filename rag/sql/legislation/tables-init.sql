CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS legislation_html
(
    id                    SERIAL PRIMARY KEY,
    act                   TEXT        NOT NULL,
    code                  TEXT        NOT NULL,
    description           TEXT        NOT NULL,
    link                  TEXT        NOT NULL,
    description_embedding VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_legislation_html_act_code ON legislation_html (act, code);
CREATE INDEX IF NOT EXISTS idx_legislation_html_description_embedding ON legislation_html USING hnsw (description_embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS legislation_html_chunks
(
    id              SERIAL PRIMARY KEY,
    act             TEXT        NOT NULL,
    code            TEXT        NOT NULL,
    content_chunk   TEXT        NOT NULL,
    chunk_embedding VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_legislation_html_chunks_act_code ON legislation_html_chunks (act, code);
CREATE INDEX IF NOT EXISTS idx_legislation_html_chunks_chunk_embedding ON legislation_html_chunks USING hnsw (chunk_embedding vector_cosine_ops);