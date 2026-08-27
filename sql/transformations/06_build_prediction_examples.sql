-- 06_build_prediction_examples.sql
-- Purpose:
--     Build historical prediction examples.

CREATE OR REPLACE TABLE processed.prediction_examples AS

WITH eligible_inspections AS (
    SELECT
        camis,
        inspection_date,
        inspection_type,
        has_critical_violation,
        score,
        grade
    FROM processed.inspections
    WHERE inspection_type LIKE 'Cycle Inspection /%'
),

examples AS (
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
        ) AS target_inspection_type,

        LEAD(has_critical_violation) OVER (
            PARTITION BY camis
            ORDER BY inspection_date
        ) AS target_critical

    FROM eligible_inspections
)

SELECT
    camis,
    cutoff_date,
    target_inspection_date,
    target_inspection_type,
    target_critical
FROM examples
WHERE target_inspection_date IS NOT NULL;