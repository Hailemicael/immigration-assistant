-- USCIS Timeline Calculator Database Schema
-- Create timeline schema
CREATE SCHEMA IF NOT EXISTS timeline;

-- Forms table
CREATE TABLE IF NOT EXISTS timeline.forms
(
    form_id     VARCHAR(20) PRIMARY KEY,
    form_name   VARCHAR(255) NOT NULL,
    description TEXT         NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Service centers table
CREATE TABLE IF NOT EXISTS timeline.service_centers
(
    center_id   SERIAL PRIMARY KEY,
    center_name VARCHAR(255) UNIQUE NOT NULL,
    shortcode   VARCHAR(10),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Form categories table
CREATE TABLE IF NOT EXISTS timeline.form_categories
(
    category_id   SERIAL PRIMARY KEY,
    form_id       VARCHAR(20)  NOT NULL REFERENCES timeline.forms (form_id),
    category_name VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (form_id, category_name)
);

-- Processing times table
CREATE TABLE IF NOT EXISTS timeline.processing_times
(
    time_id                  SERIAL PRIMARY KEY,
    form_id                  VARCHAR(20)   NOT NULL REFERENCES timeline.forms (form_id),
    center_id                INTEGER       NOT NULL REFERENCES timeline.service_centers (center_id),
    category_id              INTEGER REFERENCES timeline.form_categories (category_id),
    min_months               NUMERIC(5, 2) NOT NULL,
    max_months               NUMERIC(5, 2) NOT NULL,
    median_months            NUMERIC(5, 2) NOT NULL,
    last_updated             TIMESTAMP     NOT NULL,
    receipt_date_for_inquiry DATE,
    active                   BOOLEAN   DEFAULT TRUE,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (form_id, center_id, active) WHERE active = TRUE
);

-- User timelines table
CREATE TABLE IF NOT EXISTS timeline.user_timelines
(
    timeline_id              SERIAL PRIMARY KEY,
    form_id                  VARCHAR(20) NOT NULL REFERENCES timeline.forms (form_id),
    center_id                INTEGER     NOT NULL REFERENCES timeline.service_centers (center_id),
    category_id              INTEGER REFERENCES timeline.form_categories (category_id),
    filing_date              DATE        NOT NULL,
    earliest_completion_date DATE        NOT NULL,
    median_completion_date   DATE        NOT NULL,
    latest_completion_date   DATE        NOT NULL,
    chart_path               TEXT,
    user_ip                  VARCHAR(45),
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent history table (new)
CREATE TABLE IF NOT EXISTS timeline.agent_history
(
    history_id       SERIAL PRIMARY KEY,
    agent_name       VARCHAR(255) NOT NULL,
    generated_items  INTEGER NOT NULL,
    state_data       JSONB,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent timeline entries (new)
CREATE TABLE IF NOT EXISTS timeline.agent_timeline_entries
(
    entry_id        SERIAL PRIMARY KEY,
    history_id      INTEGER NOT NULL REFERENCES timeline.agent_history(history_id),
    form_id         VARCHAR(20) NOT NULL REFERENCES timeline.forms(form_id),
    timeline_text   TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_processing_times_form_center
    ON timeline.processing_times (form_id, center_id, active);
CREATE INDEX IF NOT EXISTS idx_user_timelines_form
    ON timeline.user_timelines (form_id);
CREATE INDEX IF NOT EXISTS idx_form_categories_form
    ON timeline.form_categories (form_id);
CREATE INDEX IF NOT EXISTS idx_agent_history_agent
    ON timeline.agent_history (agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_timeline_entries_history
    ON timeline.agent_timeline_entries (history_id);

-- Insert default service center if none exists
INSERT INTO timeline.service_centers (center_name, shortcode)
SELECT 'Default Processing Center', 'DPC'
WHERE NOT EXISTS (SELECT 1 FROM timeline.service_centers LIMIT 1);

-- Function to save timeline information from an agent
CREATE OR REPLACE FUNCTION timeline.save_agent_timeline(
    agent_name_param VARCHAR(255),
    generated_items_param INTEGER,
    state_data_param JSONB,
    timeline_entries_param JSONB
) RETURNS INTEGER AS $$
DECLARE
    new_history_id INTEGER;
    entry JSONB;
    form_id_value VARCHAR(20);
    timeline_text_value TEXT;
BEGIN
    -- Insert agent history record
    INSERT INTO timeline.agent_history
        (agent_name, generated_items, state_data)
    VALUES
        (agent_name_param, generated_items_param, state_data_param)
    RETURNING history_id INTO new_history_id;
    
    -- Process timeline entries
    FOR i IN 0..jsonb_array_length(timeline_entries_param) - 1 LOOP
        entry := timeline_entries_param->i;
        
        -- Extract form_id and timeline_text from the entry
        -- Expected format: "{form_id}: 3–6 months processing"
        form_id_value := substring(entry::TEXT, 2, position(': ' in entry::TEXT) - 2);
        timeline_text_value := entry::TEXT;
        
        -- Insert timeline entry
        INSERT INTO timeline.agent_timeline_entries
            (history_id, form_id, timeline_text)
        VALUES
            (new_history_id, form_id_value, timeline_text_value);
            
        -- Update or insert processing times for this form (assuming default service center with ID 1)
        INSERT INTO timeline.processing_times
            (form_id, center_id, min_months, median_months, max_months, last_updated)
        VALUES
            (form_id_value, 1, 3.0, 4.5, 6.0, CURRENT_TIMESTAMP)
        ON CONFLICT (form_id, center_id, active) WHERE active = TRUE
        DO UPDATE SET 
            min_months = 3.0, 
            median_months = 4.5, 
            max_months = 6.0,
            last_updated = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP;
    END LOOP;
    
    RETURN new_history_id;
END;
$$ LANGUAGE plpgsql;

-- Function to create a user timeline based on form and filing date
CREATE OR REPLACE FUNCTION timeline.create_user_timeline(
    form_id_param VARCHAR(20),
    center_id_param INTEGER DEFAULT 1,
    category_id_param INTEGER DEFAULT NULL,
    filing_date_param DATE DEFAULT CURRENT_DATE
) RETURNS INTEGER AS $$
DECLARE
    new_timeline_id INTEGER;
    min_months_value NUMERIC(5,2);
    median_months_value NUMERIC(5,2);
    max_months_value NUMERIC(5,2);
BEGIN
    -- Get the processing time values
    SELECT min_months, median_months, max_months
    INTO min_months_value, median_months_value, max_months_value
    FROM timeline.processing_times
    WHERE form_id = form_id_param
      AND center_id = center_id_param
      AND (category_id = category_id_param OR (category_id IS NULL AND category_id_param IS NULL))
      AND active = TRUE
    ORDER BY last_updated DESC
    LIMIT 1;
    
    -- If no processing time found, use default values
    IF min_months_value IS NULL THEN
        min_months_value := 3.0;
        median_months_value := 4.5;
        max_months_value := 6.0;
    END IF;
    
    -- Create user timeline
    INSERT INTO timeline.user_timelines
        (form_id, center_id, category_id, filing_date, 
         earliest_completion_date, median_completion_date, latest_completion_date)
    VALUES
        (form_id_param, center_id_param, category_id_param, filing_date_param,
         filing_date_param + (min_months_value * INTERVAL '1 month'),
         filing_date_param + (median_months_value * INTERVAL '1 month'),
         filing_date_param + (max_months_value * INTERVAL '1 month'))
    RETURNING timeline_id INTO new_timeline_id;
    
    RETURN new_timeline_id;
END;
$$ LANGUAGE plpgsql;
