-- Create schema namespace
CREATE SCHEMA IF NOT EXISTS legislation;

-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Titles
CREATE TABLE IF NOT EXISTS legislation.titles
(
    id          SERIAL PRIMARY KEY,
    title_code  TEXT UNIQUE NOT NULL,
    description TEXT        NOT NULL
);

-- Chapters
CREATE TABLE IF NOT EXISTS legislation.chapters
(
    id           SERIAL PRIMARY KEY,
    title_id     INTEGER REFERENCES legislation.titles (id),
    chapter_code TEXT NOT NULL,
    description  TEXT NOT NULL,
    UNIQUE (title_id, chapter_code)
);

-- Subchapters
CREATE TABLE IF NOT EXISTS legislation.subchapters
(
    id              SERIAL PRIMARY KEY,
    chapter_id      INTEGER REFERENCES legislation.chapters (id),
    subchapter_code TEXT NOT NULL,
    description     TEXT NOT NULL,
    UNIQUE (chapter_id, subchapter_code)
);

-- Parts
CREATE TABLE IF NOT EXISTS legislation.parts
(
    id            SERIAL PRIMARY KEY,
    subchapter_id INTEGER REFERENCES legislation.subchapters (id),
    part_code     TEXT NOT NULL,
    description   TEXT NOT NULL,
    UNIQUE (subchapter_id, part_code)
);

-- Sections
CREATE TABLE IF NOT EXISTS legislation.sections
(
    id              SERIAL PRIMARY KEY,
    part_id         INTEGER REFERENCES legislation.parts (id),
    section_code    TEXT NOT NULL,
    description     TEXT NOT NULL,
    text            TEXT NOT NULL,
    chunk_embedding VECTOR(384) NOT NULL,
    UNIQUE (part_id, section_code)
);

CREATE INDEX IF NOT EXISTS legislation_idx_sections_chunk_embedding
    ON legislation.sections USING hnsw (chunk_embedding vector_cosine_ops);

-- Subsections
CREATE TABLE IF NOT EXISTS legislation.subsections
(
    id              SERIAL PRIMARY KEY,
    section_id      INTEGER REFERENCES legislation.sections (id),
    subsection_code TEXT NOT NULL,
    title           TEXT,
    text            TEXT NOT NULL,
    chunk_embedding VECTOR(384) NOT NULL,
    UNIQUE (section_id, subsection_code)
);

CREATE INDEX IF NOT EXISTS legislation_idx_subsections_chunk_embedding
    ON legislation.subsections USING hnsw (chunk_embedding vector_cosine_ops);

-- Sub-subsections
CREATE TABLE IF NOT EXISTS legislation.sub_subsections
(
    id                  SERIAL PRIMARY KEY,
    subsection_id       INTEGER REFERENCES legislation.subsections (id),
    sub_subsection_code TEXT NOT NULL,
    title               TEXT,
    text                TEXT NOT NULL,
    chunk_embedding     VECTOR(384) NOT NULL,
    UNIQUE (subsection_id, sub_subsection_code)
);

CREATE INDEX IF NOT EXISTS legislation_idx_sub_subsections_chunk_embedding
    ON legislation.sub_subsections USING hnsw (chunk_embedding vector_cosine_ops);
