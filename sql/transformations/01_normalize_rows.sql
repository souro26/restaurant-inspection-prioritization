-- 01_normalize_rows.sql
-- Purpose:
--     Create a typed, consistently named representation of the
--     raw DOHMH restaurant-inspection source records.

CREATE SCHEMA IF NOT EXISTS processed;
CREATE OR REPLACE TABLE processed.normalized_inspection_rows AS
SELECT
    CAST(CAMIS AS VARCHAR) AS camis,
    NULLIF(TRIM(DBA), '') AS restaurant_name,
    NULLIF(TRIM(BORO), '') AS borough,
    NULLIF(TRIM(BUILDING), '') AS building,
    NULLIF(TRIM(STREET), '') AS street,
    NULLIF(TRIM(ZIPCODE), '') AS zipcode,
    NULLIF(TRIM(PHONE), '') AS phone,
    NULLIF(TRIM("CUISINE DESCRIPTION"), '') AS cuisine_description,
    TRY_CAST("INSPECTION DATE" AS DATE) AS inspection_date,
    NULLIF(TRIM(ACTION), '') AS action,
    NULLIF(TRIM("VIOLATION CODE"), '') AS violation_code,
    NULLIF(TRIM("VIOLATION DESCRIPTION"), '') AS violation_description,
    CASE
        WHEN LOWER(TRIM("CRITICAL FLAG")) = 'critical'
            THEN 'Critical'
        WHEN LOWER(TRIM("CRITICAL FLAG")) = 'not critical'
            THEN 'Not Critical'
        WHEN LOWER(TRIM("CRITICAL FLAG")) = 'not applicable'
            THEN 'Not Applicable'
        WHEN "CRITICAL FLAG" IS NULL
          OR TRIM("CRITICAL FLAG") = ''
            THEN NULL
        ELSE 'Unexpected'
    END AS critical_flag,
    TRY_CAST(SCORE AS INTEGER) AS score,
    NULLIF(TRIM(GRADE), '') AS grade,
    TRY_CAST("GRADE DATE" AS DATE) AS grade_date,
    TRY_CAST("RECORD DATE" AS DATE) AS record_date,
    NULLIF(TRIM("INSPECTION TYPE"), '') AS inspection_type,
    TRY_CAST(Latitude AS DOUBLE) AS latitude,
    TRY_CAST(Longitude AS DOUBLE) AS longitude,
    TRY_CAST("Community Board" AS VARCHAR) AS community_board,
    TRY_CAST("Council District" AS VARCHAR) AS council_district,
    TRY_CAST("Census Tract" AS VARCHAR) AS census_tract,
    TRY_CAST(BIN AS VARCHAR) AS bin,
    TRY_CAST(BBL AS VARCHAR) AS bbl,
    NULLIF(TRIM(NTA), '') AS nta,
    NULLIF(TRIM(Location) AS VARCHAR, '') AS location,
    md5(
        CONCAT_WS(
            '|',
            COALESCE(CAST(CAMIS AS VARCHAR), ''),
            COALESCE(TRIM(DBA), ''),
            COALESCE(CAST("INSPECTION DATE" AS VARCHAR), ''),
            COALESCE(TRIM("INSPECTION TYPE"), ''),
            COALESCE(TRIM("VIOLATION CODE"), ''),
            COALESCE(TRIM("VIOLATION DESCRIPTION"), ''),
            COALESCE(TRIM("CRITICAL FLAG"), ''),
            COALESCE(CAST(SCORE AS VARCHAR), ''),
            COALESCE(TRIM(GRADE), ''),
            COALESCE(CAST("GRADE DATE" AS VARCHAR), ''),
            COALESCE(TRIM(ACTION), '')
        )
    ) AS raw_row_hash
FROM raw_inspection;