CREATE OR REPLACE FUNCTION legislation.search_legislation_chunks(
    search_embedding VECTOR(1024),
    limit_count INTEGER DEFAULT 10
)
    RETURNS TABLE (
                      match_id TEXT,
                      source TEXT,
                      title TEXT,
                      chunk TEXT,
                      text_similarity FLOAT,
                      title_similarity FLOAT,
                      combined_score FLOAT
                  )
    LANGUAGE sql
AS $$
(
    SELECT
        s.id AS match_id,
        'section' AS source,
        s.title,
        s.text AS chunk,
        s.text_embedding <=> search_embedding AS text_similarity,
        s.title_embedding <=> search_embedding AS title_similarity,
        0.8 * (s.text_embedding <=> search_embedding) + 0.2 * (s.title_embedding <=> search_embedding) AS combined_score
    FROM legislation.sections s

    UNION ALL

    SELECT
        p.id AS match_id,
        'paragraph' AS source,
        p.title,
        p.text AS chunk,
        p.text_embedding <=> search_embedding AS text_similarity,
        p.title_embedding <=> search_embedding AS title_similarity,
        0.8 * (p.text_embedding <=> search_embedding) + 0.2 * (p.title_embedding <=> search_embedding) AS combined_score
    FROM legislation.paragraphs p

    ORDER BY combined_score ASC
    LIMIT limit_count
)
$$;
