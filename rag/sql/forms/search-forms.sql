CREATE OR REPLACE FUNCTION forms.find_related_immigration_documentation(
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
        WITH document_chunks AS (
            SELECT
                dc.form_id,
                dc.content_chunk,
                dc.chunk_embedding <=> search_embedding AS chunk_similarity,
                'document' AS chunk_source
            FROM forms.document_chunks dc
            WHERE dc.chunk_embedding <=> search_embedding < 0.3
        ),

             html_chunks AS (
                 SELECT
                     hc.form_id,
                     hc.content_chunk,
                     hc.chunk_embedding <=> search_embedding AS chunk_similarity,
                     'html' AS chunk_source
                 FROM forms.html_chunks hc
                 WHERE hc.chunk_embedding <=> search_embedding < 0.3
             ),

             instructions_chunks AS (
                 SELECT
                     ic.form_id,
                     ic.content_chunk,
                     ic.chunk_embedding <=> search_embedding AS chunk_similarity,
                     'instructions' AS chunk_source
                 FROM forms.instructions_chunks ic
                 WHERE ic.chunk_embedding <=> search_embedding < 0.3
             ),

             ranked_chunks AS (
                 SELECT *, ROW_NUMBER() OVER (
                     PARTITION BY form_id, content_chunk
                     ORDER BY chunk_similarity
                     ) AS chunk_rank
                 FROM (
                          SELECT * FROM document_chunks
                          UNION ALL
                          SELECT * FROM html_chunks
                          UNION ALL
                          SELECT * FROM instructions_chunks
                      ) combined_chunks
             ),

             unique_chunks AS (
                 SELECT
                     form_id,
                     content_chunk,
                     chunk_similarity,
                     chunk_source
                 FROM ranked_chunks
                 WHERE chunk_rank = 1
             ),

             best_chunk_similarity AS (
                 SELECT
                     form_id,
                     MIN(chunk_similarity) AS best_score
                 FROM unique_chunks
                 GROUP BY form_id
             ),

             metadata_matches AS (
                 SELECT
                     f.form_id,
                     d.title AS metadata_content,
                     d.title_embedding <=> search_embedding AS metadata_similarity,
                     'title' AS match_type
                 FROM forms.pdfs f
                          JOIN forms.documents d ON f.form_id = d.form_id
                 WHERE d.title_embedding <=> search_embedding < 0.4

                 UNION ALL

                 SELECT
                     f.form_id,
                     f.description AS metadata_content,
                     f.description_embedding <=> search_embedding AS metadata_similarity,
                     'description' AS match_type
                 FROM forms.pdfs f
                 WHERE f.description_embedding <=> search_embedding < 0.4
             ),

             best_metadata_match AS (
                 SELECT DISTINCT ON (form_id)
                     form_id,
                     metadata_content,
                     metadata_similarity AS best_score,
                     match_type
                 FROM metadata_matches
                 ORDER BY form_id, metadata_similarity
             ),

             combined_forms AS (
                 SELECT
                     form_id,
                     best_score AS similarity_score,
                     NULL::TEXT AS metadata_content,
                     NULL::TEXT AS match_type,
                     1 AS priority
                 FROM best_chunk_similarity

                 UNION ALL

                 SELECT
                     form_id,
                     best_score AS similarity_score,
                     metadata_content,
                     match_type,
                     2 AS priority
                 FROM best_metadata_match
                 WHERE form_id NOT IN (SELECT form_id FROM best_chunk_similarity)
             ),

             top_forms AS (
                 SELECT *
                 FROM combined_forms
                 ORDER BY priority, similarity_score
                 LIMIT limit_count
             ),

             form_details AS (
                 SELECT
                     tf.form_id,
                     tf.similarity_score,
                     tf.metadata_content,
                     tf.match_type,
                     d.file_url AS pdf_url,
                     d.title,
                     p.description,
                     i.file_url AS instructions_url,
                     tf.priority
                 FROM top_forms tf
                          JOIN forms.documents d ON tf.form_id = d.form_id
                          JOIN forms.pdfs p ON tf.form_id = p.form_id
                          LEFT JOIN (
                     SELECT form_id, MIN(file_url) AS file_url
                     FROM forms.instructions
                     GROUP BY form_id
                 ) i ON tf.form_id = i.form_id
             ),

             form_filings_ranked AS (
                 SELECT DISTINCT ON (f.form_id)
                     f.form_id,
                     f.topic_id,
                     f.category,
                     f.paper_fee,
                     f.online_fee
                 FROM forms.filings f
                          JOIN form_details fd ON f.form_id = fd.form_id
                 ORDER BY f.form_id, f.category_embedding <=> search_embedding
             ),

             form_chunks AS (
                 SELECT
                     uc.form_id,
                     uc.content_chunk,
                     uc.chunk_similarity,
                     uc.chunk_source
                 FROM unique_chunks uc
                          JOIN form_details fd ON uc.form_id = fd.form_id
                 WHERE fd.priority = 1

                 UNION ALL

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

             distinct_results AS (
                 SELECT DISTINCT ON (fd.form_id, fc.content_chunk)
                     fd.form_id,
                     fd.pdf_url,
                     fd.instructions_url,
                     fd.title,
                     fd.description,
                     fd.similarity_score,
                     fr.topic_id AS related_filing_topic_id,
                     fr.category AS related_filing_category,
                     fr.paper_fee AS related_filing_paper_fee,
                     fr.online_fee AS related_filing_online_fee,
                     fc.content_chunk,
                     fc.chunk_similarity,
                     fc.chunk_source,
                     fd.priority AS result_priority
                 FROM form_details fd
                          LEFT JOIN form_filings_ranked fr ON fd.form_id = fr.form_id
                          JOIN form_chunks fc ON fd.form_id = fc.form_id
                 ORDER BY fd.form_id, fc.content_chunk, fd.priority, fd.similarity_score, fc.chunk_similarity
             )

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
        FROM distinct_results
        ORDER BY result_priority, chunk_similarity, similarity_score;
END;
$$ LANGUAGE plpgsql;
