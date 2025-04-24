-- Ensure the schema exists
CREATE SCHEMA IF NOT EXISTS userRegist;

CREATE TABLE IF NOT EXISTS userRegist.userInfo
(
    id                     SERIAL PRIMARY KEY,
    email                  TEXT UNIQUE NOT NULL,
    first_name             TEXT        NOT NULL,
    last_name              TEXT        NOT NULL,
    summ_last_convo        TEXT,
    questions              TEXT,
    answers                TEXT
);
