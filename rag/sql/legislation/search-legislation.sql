CREATE OR REPLACE FUNCTION legislation.search_legislation_chunks(
    search_embedding VECTOR(1024),
    limit_count INTEGER DEFAULT 10,
    sim_threshold FLOAT DEFAULT 0.5
)
    RETURNS TABLE (
                      match_id TEXT,
                      title TEXT,
                      chapter TEXT,
                      subchapter TEXT,
                      chunk TEXT,
                      chunk_similarity FLOAT
                  )
    LANGUAGE sql
AS $$
WITH unified_chunks AS (
    SELECT
        CONCAT_WS('.', p.part_code, s.section_code, ss.subsection_code, sss.sub_subsection_code) AS match_id,
        t.description AS title,
        c.description AS chapter,
        sc.description AS subchapter,
        sss.text AS chunk,
        sss.chunk_embedding <=> search_embedding AS chunk_similarity
    FROM legislation.sub_subsections sss
             JOIN legislation.subsections ss ON sss.subsection_id = ss.id
             JOIN legislation.sections s ON ss.section_id = s.id
             JOIN legislation.parts p ON s.part_id = p.id
             JOIN legislation.subchapters sc ON p.subchapter_id = sc.id
             JOIN legislation.chapters c ON sc.chapter_id = c.id
             JOIN legislation.titles t ON c.title_id = t.id

    UNION ALL

    SELECT
        CONCAT_WS('.', p.part_code, s.section_code, ss.subsection_code) AS match_id,
        t.description AS title,
        c.description AS chapter,
        sc.description AS subchapter,
        ss.text AS chunk,
        ss.chunk_embedding <=> search_embedding AS chunk_similarity
    FROM legislation.subsections ss
             JOIN legislation.sections s ON ss.section_id = s.id
             JOIN legislation.parts p ON s.part_id = p.id
             JOIN legislation.subchapters sc ON p.subchapter_id = sc.id
             JOIN legislation.chapters c ON sc.chapter_id = c.id
             JOIN legislation.titles t ON c.title_id = t.id

    UNION ALL

    SELECT
        CONCAT_WS('.', p.part_code, s.section_code) AS match_id,
        t.description AS title,
        c.description AS chapter,
        sc.description AS subchapter,
        s.text AS chunk,
        s.chunk_embedding <=> search_embedding AS chunk_similarity
    FROM legislation.sections s
             JOIN legislation.parts p ON s.part_id = p.id
             JOIN legislation.subchapters sc ON p.subchapter_id = sc.id
             JOIN legislation.chapters c ON sc.chapter_id = c.id
             JOIN legislation.titles t ON c.title_id = t.id
)
SELECT *
FROM unified_chunks
WHERE chunk_similarity <= sim_threshold
ORDER BY chunk_similarity ASC
LIMIT limit_count;
$$;
