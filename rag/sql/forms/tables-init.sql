CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS form_pdfs
(
    id                   SERIAL PRIMARY KEY,
    form_id              TEXT NOT NULL,
    file_name            TEXT NOT NULL,
    file_url             TEXT NOT NULL,
    title                TEXT NOT NULL,
    description          TEXT NOT NULL,
    metadata             TEXT NOT NULL,
    is_instructions      BOOLEAN DEFAULT false,
    title_embedding      VECTOR(384) NOT NULL,
    description_embedding VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_form_pdfs_form_id ON form_pdfs (form_id);
CREATE INDEX IF NOT EXISTS idx_form_pdf_title_embedding ON form_pdfs USING hnsw (title_embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_form_pdf_description_embedding ON form_pdfs USING hnsw (description_embedding vector_cosine_ops);


CREATE TABLE IF NOT EXISTS form_pdf_chunks
(
    id              SERIAL PRIMARY KEY,
    form_id         TEXT        NOT NULL,
    form_name       TEXT        NOT NULL,
    content_chunk   TEXT        NOT NULL,
    chunk_embedding VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_form_pdf_chunks_form_id ON form_pdf_chunks (form_id);
CREATE INDEX IF NOT EXISTS idx_form_pdf_chunks_chunk_embedding ON form_pdf_chunks USING hnsw (chunk_embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS form_fees
(
    id       SERIAL PRIMARY KEY,
    form_id  TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    fee_link TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_form_fees_form_id ON form_fees (form_id);

CREATE TABLE IF NOT EXISTS form_filings
(
    id                 SERIAL PRIMARY KEY,
    form_id            TEXT        NOT NULL,
    topic_id           TEXT        NOT NULL,
    category           TEXT        NOT NULL,
    paper_fee          TEXT,
    online_fee         TEXT,
    category_embedding vector(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_form_filings_form_id ON form_filings (form_id);
CREATE INDEX IF NOT EXISTS idx_form_filings_embedding ON form_filings USING hnsw (category_embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS form_html_chunks
(
    id              SERIAL PRIMARY KEY,
    form_id         TEXT        NOT NULL,
    file_name       TEXT        NOT NULL,
    content_chunk   TEXT        NOT NULL,
    chunk_embedding VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_form_html_chunks_form_id ON form_html_chunks (form_id);
CREATE INDEX IF NOT EXISTS idx_form_html_chunks_chunk_embedding ON form_html_chunks USING hnsw (chunk_embedding vector_cosine_ops);