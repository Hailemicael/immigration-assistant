WITH title_matches AS (
    SELECT
        form_id,
        title,
        file_url,
        is_instructions,
        title_embedding <=> $1 AS title_similarity_score,
    ROW_NUMBER() OVER (ORDER BY title_embedding <=> $1) AS title_rank
FROM form_pdfs
WHERE title_embedding <=> $1 < 0.4  -- Title similarity threshold
    ),
    ranked_chunks AS (
SELECT
    c.form_id,
    c.content_chunk,
    c.chunk_embedding <=> $1 AS similarity_score,
    ROW_NUMBER() OVER (PARTITION BY c.form_id ORDER BY c.chunk_embedding <=> $1) AS rank
FROM form_pdf_chunks c
WHERE c.chunk_embedding <=> $1 < 0.3  -- Content similarity threshold
UNION ALL
SELECT
    h.form_id,
    h.content_chunk,
    h.chunk_embedding <=> $1 AS similarity_score,
    ROW_NUMBER() OVER (PARTITION BY h.form_id ORDER BY h.chunk_embedding <=> $1) AS rank
FROM form_html_chunks h
WHERE h.chunk_embedding <=> $1 < 0.3  -- Content similarity threshold
    ),
    form_links AS (
SELECT
    p.form_id,
    MAX(CASE WHEN NOT p.is_instructions THEN p.file_url END) AS form_url,
    MAX(CASE WHEN p.is_instructions THEN p.file_url END) AS instructions_url,
    MAX(CASE WHEN NOT p.is_instructions THEN p.title END) AS form_title,
    MIN(CASE WHEN p.title_embedding <=> $1 < 0.4 THEN p.title_embedding <=> $1 ELSE 1 END) AS best_title_score
FROM form_pdfs p
GROUP BY p.form_id
    ),
    closest_fees AS (
SELECT
    f.form_id,
    f.topic_id,
    f.category,
    f.paper_fee,
    f.online_fee,
    f.category_embedding <=> $1 AS fee_similarity_score,
    ROW_NUMBER() OVER (PARTITION BY f.form_id ORDER BY f.category_embedding <=> $1) AS fee_rank
FROM form_filings f
    ),
    combined_results AS (
-- Results from content chunks
SELECT
    rc.form_id,
    fl.form_title,
    rc.content_chunk,
    rc.similarity_score AS content_similarity,
    fl.best_title_score AS title_similarity,
    (rc.similarity_score + fl.best_title_score) / 2 AS combined_score,
    fl.form_url,
    fl.instructions_url,
    cf.category,
    cf.topic_id,
    cf.paper_fee,
    cf.online_fee,
    cf.fee_similarity_score,
    rc.rank
FROM ranked_chunks rc
    JOIN form_links fl ON rc.form_id = fl.form_id
    LEFT JOIN closest_fees cf ON rc.form_id = cf.form_id AND cf.fee_rank = 1
WHERE rc.rank <= 3  -- Return top 3 chunks per form

UNION ALL

-- Results from title matches (even if no content match)
SELECT
    tm.form_id,
    tm.title AS form_title,
    NULL AS content_chunk,
    1 AS content_similarity,  -- Default content similarity
    tm.title_similarity_score AS title_similarity,
    tm.title_similarity_score AS combined_score,  -- Prioritize by title score
    CASE WHEN NOT tm.is_instructions THEN tm.file_url ELSE NULL END AS form_url,
    CASE WHEN tm.is_instructions THEN tm.file_url ELSE NULL END AS instructions_url,
    cf.category,
    cf.topic_id,
    cf.paper_fee,
    cf.online_fee,
    cf.fee_similarity_score,
    1 AS rank
FROM title_matches tm
    LEFT JOIN closest_fees cf ON tm.form_id = cf.form_id AND cf.fee_rank = 1
WHERE tm.title_rank <= 5  -- Get top 5 title matches
  AND NOT EXISTS (
    SELECT 1 FROM ranked_chunks rc
    WHERE rc.form_id = tm.form_id
    )  -- Only include forms not already matched by content
    )
SELECT * FROM combined_results
ORDER BY combined_score, form_id, rank
    LIMIT $2