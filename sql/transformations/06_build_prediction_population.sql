-- 06_build_prediction_population.sql
-- Purpose:
--     Build the historical prediction population.

CREATE OR REPLACE TABLE processed.prediction_population AS

WITH eligible_inspections AS (
    SELECT
        camis,
        inspection_date,
        inspection_type
    FROM processed.inspections
    WHERE inspection_type LIKE 'Cycle Inspection /%'
),

population AS (
    SELECT
        camis,
        inspection_date AS cutoff_date,

        LEAD(inspection_date) OVER (
            PARTITION BY camis
            ORDER BY inspection_date
        ) AS target_inspection_date,

        LEAD(inspection_type) OVER (
            PARTITION BY camis
            ORDER BY inspection_date
        ) AS target_inspection_type

    FROM eligible_inspections
)

SELECT
    camis,
    cutoff_date,
    target_inspection_date,
    target_inspection_type
FROM population
WHERE target_inspection_date IS NOT NULL;