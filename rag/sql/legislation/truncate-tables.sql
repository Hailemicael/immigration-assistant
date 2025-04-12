CREATE OR REPLACE PROCEDURE truncate_legislation_tables()
    LANGUAGE plpgsql
AS $$
BEGIN
    Truncate table legislation_html cascade;

    Truncate table legislation_html_chunks cascade;


    RAISE NOTICE 'All immigration legislation tables have been truncated successfully.';
END;
$$;