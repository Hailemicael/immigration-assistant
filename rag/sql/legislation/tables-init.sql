-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Schema namespace
CREATE SCHEMA IF NOT EXISTS legislation;

-- Sections Table
CREATE TABLE IF NOT EXISTS legislation.sections
(
    id              TEXT PRIMARY KEY,
    citation        TEXT,
    title           TEXT NOT NULL,
    text            TEXT NOT NULL,
    title_embedding VECTOR(1024),
    text_embedding  VECTOR(1024)
);
-- HNSW Indexes for vector search
CREATE INDEX IF NOT EXISTS sections_title_embedding_hnsw_idx
    ON legislation.sections USING hnsw (title_embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS sections_text_embedding_hnsw_idx
    ON legislation.sections USING hnsw (text_embedding vector_cosine_ops);

-- Paragraphs Table
CREATE TABLE IF NOT EXISTS legislation.paragraphs
(
    id              TEXT PRIMARY KEY,
    section_id      TEXT REFERENCES legislation.sections (id) ON DELETE CASCADE,
    title           TEXT,
    text            TEXT NOT NULL,
    title_embedding VECTOR(1024),
    text_embedding  VECTOR(1024)
);

-- HNSW Indexes for vector search

CREATE INDEX IF NOT EXISTS paragraphs_title_embedding_hnsw_idx
    ON legislation.paragraphs USING hnsw (title_embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS paragraphs_text_embedding_hnsw_idx
    ON legislation.paragraphs USING hnsw (text_embedding vector_cosine_ops);