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
    related_filing_online_fee TEXT,
    content_chunk TEXT,
    chunk_similarity FLOAT,
    chunk_source TEXT
) AS $$
#variable_conflict use_column
BEGIN
RETURN QUERY
    WITH pdf_chunks AS (
        -- Find forms with similar PDF chunks
        SELECT
            fpc.form_id,
            fpc.content_chunk,
            fpc.chunk_embedding <=> search_embedding AS chunk_similarity,
            'pdf' AS chunk_source
        FROM form_pdf_chunks fpc
        WHERE fpc.chunk_embedding <=> search_embedding < 0.3
    ),

    html_chunks AS (
        -- Find forms with similar HTML chunks
        SELECT
            fhc.form_id,
            fhc.content_chunk,
            fhc.chunk_embedding <=> search_embedding AS chunk_similarity,
            'html' AS chunk_source
        FROM form_html_chunks fhc
        WHERE fhc.chunk_embedding <=> search_embedding < 0.3
    ),

    -- Combine all chunks and rank them within each form
    ranked_chunks AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY form_id, content_chunk
                ORDER BY chunk_similarity
            ) as chunk_rank
        FROM (
            SELECT * FROM pdf_chunks
            UNION ALL
            SELECT * FROM html_chunks
        ) combined_chunks
    ),

    -- Keep only one instance of each chunk text per form
    unique_chunks AS (
        SELECT
            form_id,
            content_chunk,
            chunk_similarity,
            chunk_source
        FROM ranked_chunks
        WHERE chunk_rank = 1
    ),

    -- Get the best chunk similarity per form
    best_chunk_similarity AS (
        SELECT
            uc.form_id,
            MIN(uc.chunk_similarity) AS best_score
        FROM unique_chunks uc
        GROUP BY uc.form_id
    ),

    -- Secondary matches based on form metadata
    metadata_matches AS (
        -- Title matches (secondary relevance)
        SELECT
            fp.form_id,
            fp.title AS metadata_content,
            fp.title_embedding <=> search_embedding AS metadata_similarity,
            'title' AS match_type
        FROM form_pdfs fp
        WHERE fp.title_embedding <=> search_embedding < 0.4

        UNION ALL

        -- Description matches (secondary relevance)
        SELECT
            fp.form_id,
            fp.description AS metadata_content,
            fp.description_embedding <=> search_embedding AS metadata_similarity,
            'description' AS match_type
        FROM form_pdfs fp
        WHERE fp.description_embedding <=> search_embedding < 0.4
    ),

    -- Get the best metadata match per form
    best_metadata_match AS (
        SELECT DISTINCT ON (mm.form_id)
            mm.form_id,
            mm.metadata_content,
            mm.metadata_similarity AS best_score,
            mm.match_type
        FROM metadata_matches mm
        ORDER BY mm.form_id, mm.metadata_similarity
    ),

    -- Combine primary and secondary matches, prioritizing chunk matches
    combined_forms AS (
        -- Primary matches (forms with matching chunks)
        SELECT
            bcs.form_id,
            bcs.best_score AS similarity_score,
            NULL::TEXT AS metadata_content,
            NULL::TEXT AS match_type,
            1 AS priority  -- Higher priority
        FROM best_chunk_similarity bcs

        UNION ALL

        -- Secondary matches (forms with matching metadata but no chunks)
        SELECT
            bmm.form_id,
            bmm.best_score AS similarity_score,
            bmm.metadata_content,
            bmm.match_type,
            2 AS priority  -- Lower priority
        FROM best_metadata_match bmm
        WHERE bmm.form_id NOT IN (SELECT bcs.form_id FROM best_chunk_similarity bcs)
    ),

    -- Get the top N distinct forms based on relevance
    top_forms AS (
        SELECT
            cf.form_id,
            cf.similarity_score,
            cf.metadata_content,
            cf.match_type,
            cf.priority
        FROM combined_forms cf
        ORDER BY cf.priority, cf.similarity_score
        LIMIT limit_count
    ),

    -- Get form details
    form_details AS (
        SELECT
            tf.form_id,
            tf.similarity_score,
            tf.metadata_content,
            tf.match_type,
            fp.file_url AS pdf_url,
            fp.title,
            fp.description,
            instructions.file_url AS instructions_url,
            tf.priority
        FROM top_forms tf
        JOIN form_pdfs fp ON tf.form_id = fp.form_id
        LEFT JOIN (
            SELECT fp_inst.form_id, MIN(fp_inst.file_url) AS file_url
            FROM form_pdfs fp_inst
            WHERE fp_inst.is_instructions = true
            GROUP BY fp_inst.form_id
        ) instructions ON tf.form_id = instructions.form_id
    ),

    -- Get related form filings (one per form)
    form_filings_ranked AS (
        SELECT DISTINCT ON (ff.form_id)
            ff.form_id,
            ff.topic_id,
            ff.category,
            ff.paper_fee,
            ff.online_fee
        FROM form_filings ff
        JOIN form_details fd ON ff.form_id = fd.form_id
        ORDER BY ff.form_id, ff.category_embedding <=> search_embedding
    ),

    -- Get chunks for top forms
    form_chunks AS (
        -- For forms with chunk matches, get their unique chunks
        SELECT
            uc.form_id,
            uc.content_chunk,
            uc.chunk_similarity,
            uc.chunk_source
        FROM unique_chunks uc
        JOIN form_details fd ON uc.form_id = fd.form_id
        WHERE fd.priority = 1

        UNION ALL

        -- For forms matched via metadata, show the metadata as the chunk
        SELECT
            fd.form_id,
            CASE
                WHEN fd.match_type = 'title' THEN 'Title: ' || fd.metadata_content
                WHEN fd.match_type = 'description' THEN 'Description: ' || fd.metadata_content
                ELSE fd.metadata_content
            END AS content_chunk,
            fd.similarity_score AS chunk_similarity,
            fd.match_type AS chunk_source
        FROM form_details fd
        WHERE fd.priority = 2
    ),

    -- Final combined result with distinct form_id and content_chunk combinations
    distinct_results AS (
        SELECT DISTINCT ON (fd.form_id, fc.content_chunk)
            fd.form_id,
            fd.pdf_url,
            fd.instructions_url,
            fd.title,
            fd.description,
            fd.similarity_score,
            ffr.topic_id AS related_filing_topic_id,
            ffr.category AS related_filing_category,
            ffr.paper_fee AS related_filing_paper_fee,
            ffr.online_fee AS related_filing_online_fee,
            fc.content_chunk,
            fc.chunk_similarity,
            fc.chunk_source,
            fd.priority AS result_priority
        FROM form_details fd
        LEFT JOIN form_filings_ranked ffr ON fd.form_id = ffr.form_id
        JOIN form_chunks fc ON fd.form_id = fc.form_id
        ORDER BY fd.form_id, fc.content_chunk, fd.priority, fd.similarity_score, fc.chunk_similarity
    )

-- Return the final distinct results ordered by relevance
SELECT
    form_id,
    pdf_url,
    instructions_url,
    title,
    description,
    similarity_score,
    related_filing_topic_id,
    related_filing_category,
    related_filing_paper_fee,
    related_filing_online_fee,
    content_chunk,
    chunk_similarity,
    chunk_source
FROM distinct_results dr
ORDER BY dr.result_priority, dr.chunk_similarity, dr.similarity_score;
END;
$$ LANGUAGE plpgsql;