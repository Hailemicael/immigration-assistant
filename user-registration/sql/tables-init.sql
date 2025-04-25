-- Ensure the schema exists
CREATE SCHEMA IF NOT EXISTS users;

CREATE TABLE IF NOT EXISTS users.userInfo
(
    id                     SERIAL PRIMARY KEY,
    email                  TEXT UNIQUE NOT NULL,
    first_name             TEXT        NOT NULL,
    last_name              TEXT        NOT NULL,
    summ_last_convo        TEXT,
    questions              TEXT,
    answers                TEXT
);
