WITH description_matches AS (
    SELECT
        act,
        code,
        description,
        link,
        description_embedding <=> $1 AS description_similarity,
        ROW_NUMBER() OVER (ORDER BY description_embedding <=> $1) AS description_rank
    FROM legislation_html
    WHERE description_embedding <=> $1 < 0.4  -- Description similarity threshold
),
     ranked_chunks AS (
         SELECT
             act,
             code,
             content_chunk,
             chunk_embedding <=> $1 AS similarity_score,
             ROW_NUMBER() OVER (PARTITION BY act, code ORDER BY chunk_embedding <=> $1) AS rank
         FROM legislation_html_chunks
         WHERE chunk_embedding <=> $1 < 0.3  -- Content similarity threshold
     ),
     combined_results AS (
         -- Results from content chunks
         SELECT
             rc.act,
             rc.code,
             l.description,
             rc.content_chunk,
             rc.similarity_score AS content_similarity,
             l.description_embedding <=> $1 AS description_similarity,
             CASE
                 WHEN rc.similarity_score < 0.3 AND l.description_embedding <=> $1 < 0.4
                     THEN (rc.similarity_score + (l.description_embedding <=> $1)) / 2  -- Average when both match
                 WHEN rc.similarity_score < 0.3
                     THEN rc.similarity_score  -- Content only match
                 ELSE l.description_embedding <=> $1  -- Description only match
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
             1 AS rank,
             'description' AS match_source
         FROM description_matches dm
         WHERE dm.description_rank <= 5  -- Get top 5 description matches
           AND NOT EXISTS (
             SELECT 1 FROM ranked_chunks rc
             WHERE rc.act = dm.act AND rc.code = dm.code
         )  -- Only include legislation not already matched by content
     )
SELECT * FROM combined_results
ORDER BY combined_score, act, code, rank
LIMIT $2