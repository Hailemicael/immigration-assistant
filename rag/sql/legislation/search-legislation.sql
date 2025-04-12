CREATE OR REPLACE FUNCTION find_related_legislation(
    search_embedding VECTOR(384),
    limit_count INTEGER DEFAULT 10
)
    RETURNS TABLE (
                      act TEXT,
                      code TEXT,
                      description TEXT,
                      content_chunk TEXT,
                      content_similarity FLOAT,
                      description_similarity FLOAT,
                      combined_score FLOAT,
                      link TEXT,
                      rank INTEGER,
                      match_source TEXT
                  ) AS $$
BEGIN
    RETURN QUERY
        WITH description_matches AS (
            SELECT
                lh.act,
                lh.code,
                lh.description,
                lh.link,
                lh.description_embedding <=> search_embedding AS description_similarity,
                ROW_NUMBER() OVER (ORDER BY lh.description_embedding <=> search_embedding)::INTEGER AS description_rank
            FROM legislation_html lh
            WHERE lh.description_embedding <=> search_embedding < 0.4  -- Description similarity threshold
        ),
             ranked_chunks AS (
                 SELECT
                     lhc.act,
                     lhc.code,
                     lhc.content_chunk,
                     lhc.chunk_embedding <=> search_embedding AS similarity_score,
                     ROW_NUMBER() OVER (PARTITION BY lhc.act, lhc.code ORDER BY lhc.chunk_embedding <=> search_embedding)::INTEGER AS rank
                 FROM legislation_html_chunks lhc
                 WHERE lhc.chunk_embedding <=> search_embedding < 0.3  -- Content similarity threshold
             ),
             combined_results AS (
                 -- Results from content chunks
                 SELECT
                     rc.act,
                     rc.code,
                     l.description,
                     rc.content_chunk,
                     rc.similarity_score AS content_similarity,
                     l.description_embedding <=> search_embedding AS description_similarity,
                     CASE
                         WHEN rc.similarity_score < 0.3 AND l.description_embedding <=> search_embedding < 0.4
                             THEN (rc.similarity_score + (l.description_embedding <=> search_embedding)) / 2  -- Average when both match
                         WHEN rc.similarity_score < 0.3
                             THEN rc.similarity_score  -- Content only match
                         ELSE l.description_embedding <=> search_embedding  -- Description only match
                         END AS combined_score,
                     l.link,
                     rc.rank,
                     'content' AS match_source
                 FROM ranked_chunks rc
                          JOIN legislation_html l ON rc.act = l.act AND rc.code = l.code
                 WHERE rc.rank <= 3  -- Return top 3 chunks per legislation

                 UNION ALL

                 -- Results from description matches (even if no content match)
                 SELECT
                     dm.act,
                     dm.code,
                     dm.description,
                     NULL AS content_chunk,
                     1 AS content_similarity,  -- Default content similarity
                     dm.description_similarity,
                     dm.description_similarity AS combined_score,
                     dm.link,
                     1::INTEGER AS rank,
                     'description' AS match_source
                 FROM description_matches dm
                 WHERE dm.description_rank <= 5  -- Get top 5 description matches
                   AND NOT EXISTS (
                     SELECT 1 FROM ranked_chunks rc
                     WHERE rc.act = dm.act AND rc.code = dm.code
                 )  -- Only include legislation not already matched by content
             )
        SELECT
            cr.act,
            cr.code,
            cr.description,
            cr.content_chunk,
            cr.content_similarity,
            cr.description_similarity,
            cr.combined_score,
            cr.link,
            cr.rank::INTEGER,
            cr.match_source
        FROM combined_results cr
        ORDER BY cr.combined_score, cr.act, cr.code, cr.rank
        LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;