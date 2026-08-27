-- 1. Source Size

SELECT  
    COUNT(*) AS total_rows, 
    COUNT(DISTINCT CAMIS) AS unique_restaurants
FROM raw_inspection;

-- 2. Timespan Covered

SELECT
    MIN("INSPECTION DATE") AS earliest_inspection,
    MAX("INSPECTION DATE") AS latest_inspection,
    MIN("RECORD DATE") AS earliest_record,
    MAX("RECORD DATE") AS latest_record
FROM raw_inspection;

--3. Records not inspected yet

SELECT COUNT(*) as not_yet_inspected_rows 
FROM raw_inspection 
WHERE "INSPECTION DATE" = DATE '1900-01-01';

--4. Missing Values

SELECT
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE CAMIS IS NULL) AS null_camis,
    COUNT(*) FILTER (WHERE DBA IS NULL) AS null_dba,
    COUNT(*) FILTER (WHERE BORO IS NULL) AS null_boro,
    COUNT(*) FILTER (WHERE "INSPECTION DATE" IS NULL) AS null_inspection_date,
    COUNT(*) FILTER (WHERE ACTION IS NULL) AS null_action,
    COUNT(*) FILTER (WHERE "VIOLATION CODE" IS NULL) AS null_violation_code,
    COUNT(*) FILTER (WHERE "VIOLATION DESCRIPTION" IS NULL)
        AS null_violation_description,
    COUNT(*) FILTER (WHERE "CRITICAL FLAG" IS NULL)
        AS null_critical_flag,
    COUNT(*) FILTER (WHERE SCORE IS NULL) AS null_score,
    COUNT(*) FILTER (WHERE GRADE IS NULL) AS null_grade,
    COUNT(*) FILTER (WHERE "GRADE DATE" IS NULL) AS null_grade_date,
    COUNT(*) FILTER (WHERE "INSPECTION TYPE" IS NULL)
        AS null_inspection_type
FROM raw_inspection;

--5. Duplicates

SELECT
    total_rows,
    unique_rows,
    total_rows - unique_rows AS duplicate_rows
FROM (
    SELECT
        (SELECT COUNT(*) FROM raw_inspection) AS total_rows,
        (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw_inspection)) AS unique_rows
);

--6. Row grain 

SELECT
    COUNT(DISTINCT (
        CAMIS,
        "INSPECTION DATE",
        "INSPECTION TYPE"
    )) AS inspection_groups
FROM raw_inspection;

--7. Group Sizes

SELECT
    CAMIS,
    "INSPECTION DATE",
    "INSPECTION TYPE",
    COUNT(*) AS raw_rows
FROM raw_inspection
GROUP BY
    CAMIS,
    "INSPECTION DATE",
    "INSPECTION TYPE"
ORDER BY raw_rows DESC
LIMIT 20;