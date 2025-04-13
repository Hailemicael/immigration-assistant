CREATE OR REPLACE PROCEDURE truncate_legislation_tables()
    LANGUAGE plpgsql
AS $$
BEGIN
    TRUNCATE TABLE
        legislation.sub_subsections,
        legislation.subsections,
        legislation.sections,
        legislation.parts,
        legislation.subchapters,
        legislation.chapters,
        legislation.titles
        CASCADE;

    RAISE NOTICE 'All legislation schema tables have been truncated successfully.';
END;
$$;