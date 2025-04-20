CREATE OR REPLACE PROCEDURE truncate_legislation_tables()
    LANGUAGE plpgsql
AS $$
BEGIN
    TRUNCATE TABLE
        legislation.paragraphs,
        legislation.sections,
        CASCADE;

    RAISE NOTICE 'All legislation schema tables have been truncated successfully.';
END;
$$;