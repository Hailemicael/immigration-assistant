CREATE OR REPLACE PROCEDURE truncate_immigration_tables()
    LANGUAGE plpgsql
AS $$
BEGIN
    TRUNCATE TABLE form_pdfs CASCADE;
    TRUNCATE TABLE form_pdf_chunks CASCADE;
    TRUNCATE TABLE form_fees CASCADE;
    TRUNCATE TABLE form_filings CASCADE;
    TRUNCATE TABLE form_html_chunks CASCADE;

    RAISE NOTICE 'All immigration form tables have been truncated successfully.';
END;
$$;