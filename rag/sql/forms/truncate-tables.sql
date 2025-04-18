CREATE OR REPLACE PROCEDURE truncate_forms_tables()
    LANGUAGE plpgsql
AS $$
BEGIN
    TRUNCATE TABLE
        forms.pdfs,
        forms.documents,
        forms.document_chunks,
        forms.instructions,
        forms.instructions_chunks,
        forms.fees,
        forms.filings,
        forms.html_chunks
        CASCADE;

    RAISE NOTICE 'All immigration form tables have been truncated successfully.';
END;
$$;