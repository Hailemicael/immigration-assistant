CREATE OR REPLACE FUNCTION find_related_immigration_documentation(
    search_embedding VECTOR(384),
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    form_id TEXT,
    pdf_url TEXT,
    instructions_url TEXT,
    title TEXT,
    description TEXT,
    similarity_score FLOAT,
    related_filing_topic_id TEXT,
    related_filing_category TEXT,
    related_filing_paper_fee TEXT,
    related_filing_online_fee TEXT
) AS $$
BEGIN
RETURN QUERY
    WITH ranked_forms AS (
        -- Find forms with similar title embeddings
        SELECT
            form_id,
            file_url,
            title,
            description,
            CASE WHEN is_instructions THEN file_url ELSE NULL END AS instructions_url,
            (title_embedding <=> search_embedding) AS title_similarity_score,
            1 AS source_type  -- 1 for title match
        FROM form_pdfs
        WHERE title_embedding <=> search_embedding < 0.3

        UNION ALL

        -- Find forms with similar description embeddings
        SELECT
            form_id,
            file_url,
            title,
            description,
            CASE WHEN is_instructions THEN file_url ELSE NULL END AS instructions_url,
            (description_embedding <=> search_embedding) AS description_similarity_score,
            2 AS source_type  -- 2 for description match
        FROM form_pdfs
        WHERE description_embedding <=> search_embedding < 0.3

        UNION ALL

        -- Find forms with similar content chunks
        SELECT
            fpc.form_id,
            fp.file_url,
            fp.title,
            fp.description,
            CASE WHEN fp.is_instructions THEN fp.file_url ELSE NULL END AS instructions_url,
            (fpc.chunk_embedding <=> search_embedding) AS chunk_similarity_score,
            3 AS source_type  -- 3 for content chunk match
        FROM form_pdf_chunks fpc
        JOIN form_pdfs fp ON fpc.form_id = fp.form_id
        WHERE fpc.chunk_embedding <=> search_embedding < 0.3

        UNION ALL

        -- Find forms with similar HTML content chunks
        SELECT
            fhc.form_id,
            fp.file_url,
            fp.title,
            fp.description,
            CASE WHEN fp.is_instructions THEN fp.file_url ELSE NULL END AS instructions_url,
            (fhc.chunk_embedding <=> search_embedding) AS html_chunk_similarity_score,
            4 AS source_type  -- 4 for HTML chunk match
        FROM form_html_chunks fhc
        JOIN form_pdfs fp ON fhc.form_id = fp.form_id
        WHERE fhc.chunk_embedding <=> search_embedding < 0.3
    ),

    -- Get the best match score for each form
    aggregated_forms AS (
        SELECT
            form_id,
            file_url,
            title,
            description,
            MIN(
                CASE
                    WHEN source_type = 1 THEN title_similarity_score
                    WHEN source_type = 2 THEN description_similarity_score
                    WHEN source_type = 3 THEN chunk_similarity_score
                    WHEN source_type = 4 THEN html_chunk_similarity_score
                END
            ) AS best_score
        FROM ranked_forms
        GROUP BY form_id, file_url, title, description
    ),

    -- Add in the instructions URL for each form
    forms_with_instructions AS (
        SELECT
            af.form_id,
            af.file_url AS pdf_url,
            af.title,
            af.description,
            instructions.file_url AS instructions_url,
            af.best_score
        FROM aggregated_forms af
        LEFT JOIN (
            SELECT form_id, file_url
            FROM form_pdfs
            WHERE is_instructions = true
        ) instructions ON af.form_id = instructions.form_id
    ),

    -- Get related form filings for each form
    form_filings_ranked AS (
        SELECT
            ff.form_id,
            ff.topic_id,
            ff.category,
            ff.paper_fee,
            ff.online_fee,
            (ff.category_embedding <=> search_embedding) AS similarity_score,
            ROW_NUMBER() OVER (PARTITION BY ff.form_id ORDER BY ff.category_embedding <=> search_embedding) AS rank
        FROM form_filings ff
        WHERE ff.form_id IN (SELECT form_id FROM forms_with_instructions)
    )

-- Final result combining forms and their top related filing
SELECT
    f.form_id,
    f.pdf_url,
    f.instructions_url,
    f.title,
    f.description,
    f.best_score AS similarity_score,
    ff.topic_id AS related_filing_topic_id,
    ff.category AS related_filing_category,
    ff.paper_fee AS related_filing_paper_fee,
    ff.online_fee AS related_filing_online_fee
FROM forms_with_instructions f
         LEFT JOIN form_filings_ranked ff ON f.form_id = ff.form_id AND ff.rank = 1
ORDER BY f.best_score
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;