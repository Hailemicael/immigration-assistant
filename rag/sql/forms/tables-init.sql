-- Ensure the schema exists
CREATE SCHEMA IF NOT EXISTS forms;

-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- forms.pdfs (high-level form metadata)
CREATE TABLE IF NOT EXISTS forms.pdfs
(
    id                    SERIAL PRIMARY KEY,
    form_id               TEXT UNIQUE NOT NULL,
    description           TEXT        NOT NULL,
    description_embedding VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pdfs_form_id
    ON forms.pdfs (form_id);

CREATE INDEX IF NOT EXISTS idx_pdfs_description_embedding
    ON forms.pdfs USING hnsw (description_embedding vector_cosine_ops);


-- forms.documents (individual document files)
CREATE TABLE IF NOT EXISTS forms.documents
(
    id                    SERIAL PRIMARY KEY,
    form_id               TEXT        NOT NULL REFERENCES forms.pdfs (form_id),
    file_name             TEXT        NOT NULL,
    file_url              TEXT        NOT NULL,
    title                 TEXT        NOT NULL,
    metadata              TEXT        NOT NULL,
    title_embedding       VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_form_id
    ON forms.documents (form_id);

CREATE INDEX IF NOT EXISTS idx_documents_title_embedding
    ON forms.documents USING hnsw (title_embedding vector_cosine_ops);

-- forms.document_chunks
CREATE TABLE IF NOT EXISTS forms.document_chunks
(
    id              SERIAL PRIMARY KEY,
    form_id         TEXT        NOT NULL REFERENCES forms.pdfs (form_id),
    form_name       TEXT        NOT NULL,
    content_chunk   TEXT        NOT NULL,
    chunk_embedding VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_form_id
    ON forms.document_chunks (form_id);

CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
    ON forms.document_chunks USING hnsw (chunk_embedding vector_cosine_ops);

-- forms.instructions
CREATE TABLE IF NOT EXISTS forms.instructions
(
    id          SERIAL PRIMARY KEY,
    form_id     TEXT NOT NULL REFERENCES forms.pdfs (form_id),
    file_name   TEXT NOT NULL,
    file_url    TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    metadata    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_instructions_form_id
    ON forms.instructions (form_id);

-- forms.instructions_chunks
CREATE TABLE IF NOT EXISTS forms.instructions_chunks
(
    id              SERIAL PRIMARY KEY,
    form_id         TEXT        NOT NULL REFERENCES forms.pdfs (form_id),
    form_name       TEXT        NOT NULL,
    content_chunk   TEXT        NOT NULL,
    chunk_embedding VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_instructions_chunks_form_id
    ON forms.instructions_chunks (form_id);

CREATE INDEX IF NOT EXISTS idx_instructions_chunks_embedding
    ON forms.instructions_chunks USING hnsw (chunk_embedding vector_cosine_ops);

-- forms.fees
CREATE TABLE IF NOT EXISTS forms.fees
(
    id       SERIAL PRIMARY KEY,
    form_id  TEXT NOT NULL REFERENCES forms.pdfs (form_id),
    topic_id TEXT NOT NULL,
    fee_link TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fees_form_id
    ON forms.fees (form_id);

-- forms.filings
CREATE TABLE IF NOT EXISTS forms.filings
(
    id                 SERIAL PRIMARY KEY,
    form_id            TEXT        NOT NULL REFERENCES forms.pdfs (form_id),
    topic_id           TEXT        NOT NULL,
    category           TEXT        NOT NULL,
    paper_fee          TEXT,
    online_fee         TEXT,
    category_embedding VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_filings_form_id
    ON forms.filings (form_id);

CREATE INDEX IF NOT EXISTS idx_filings_embedding
    ON forms.filings USING hnsw (category_embedding vector_cosine_ops);

-- forms.html_chunks
CREATE TABLE IF NOT EXISTS forms.html_chunks
(
    id              SERIAL PRIMARY KEY,
    form_id         TEXT        NOT NULL REFERENCES forms.pdfs (form_id),
    file_name       TEXT        NOT NULL,
    content_chunk   TEXT        NOT NULL,
    chunk_embedding VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_html_chunks_form_id
    ON forms.html_chunks (form_id);

CREATE INDEX IF NOT EXISTS idx_html_chunks_embedding
    ON forms.html_chunks USING hnsw (chunk_embedding vector_cosine_ops);
