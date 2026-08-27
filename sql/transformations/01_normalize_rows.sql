-- 01_normalize_rows.sql
-- Purpose:
--     Create a normalized representation of the raw DOHMH inspection records.

CREATE SCHEMA IF NOT EXISTS processed;

CREATE OR REPLACE TABLE processed.normalized_inspection_rows AS
SELECT
    CAMIS AS camis,
    DBA AS restaurant_name,
    BORO AS borough,
    BUILDING AS building,
    STREET AS street,
    ZIPCODE AS zipcode,
    PHONE AS phone,
    "CUISINE DESCRIPTION" AS cuisine_description,
    "INSPECTION DATE" AS inspection_date,
    ACTION AS action,
    "VIOLATION CODE" AS violation_code,
    "VIOLATION DESCRIPTION" AS violation_description,
    "CRITICAL FLAG" AS critical_flag,
    SCORE AS score,
    GRADE AS grade,
    "GRADE DATE" AS grade_date,
    "RECORD DATE" AS record_date,
    "INSPECTION TYPE" AS inspection_type,
    Latitude AS latitude,
    Longitude AS longitude,
    "Community Board" AS community_board,
    "Council District" AS council_district,
    "Census Tract" AS census_tract,
    BIN AS bin,
    BBL AS bbl,
    NTA AS nta,
    Location AS location
FROM raw_inspection;