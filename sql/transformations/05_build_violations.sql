
-- 05_build_violations.sql
-- Purpose:
--     Build the cleaned violation-level table.

CREATE OR REPLACE TABLE processed.violations AS
SELECT
    md5(
        CONCAT_WS(
            '|',
            camis,
            CAST(inspection_date AS VARCHAR),
            COALESCE(inspection_type, 'UNKNOWN')
        )
    ) AS inspection_id,
    camis,
    inspection_date,
    COALESCE(inspection_type, 'UNKNOWN') AS inspection_type,
    violation_code,
    violation_description,
    critical_flag,
    CASE
        WHEN critical_flag = 'Critical' THEN TRUE
        ELSE FALSE
    END AS is_critical_violation
FROM processed.deduplicated_inspection_rows
WHERE camis IS NOT NULL
  AND inspection_date IS NOT NULL
  AND inspection_date <> DATE '1900-01-01'
  AND violation_code IS NOT NULL;